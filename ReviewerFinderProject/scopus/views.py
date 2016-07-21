# "Balance disorder"
from rest_framework.renderers import JSONRenderer, StaticHTMLRenderer
from rest_framework import exceptions
import requests, json, re
from rest_framework.views import APIView
from rest_framework.response import Response
from django.conf import settings
from rest_framework.permissions import IsAuthenticated
from datetime import date
from time import time
from fake_useragent import UserAgent
import sys, logging, threading


class ScopusView(APIView):
	# Below line commented for testing purpose. Once uncommented, only database user can access it.
	# authentication_classes = (BasicAuthentication,)
	permission_classes = (IsAuthenticated,)
	def __init__(self):
		self.ua = UserAgent()
		self.NO_OF_SEARCH_RESULT = 6
		self.NO_OF_SEARCH_COUNT = 10
		logging.basicConfig(filename='{}.log'.format(__name__), level=logging.DEBUG, format='(%(threadName)-9s) %('
																							'message)s',)

	renderer_classes = (JSONRenderer,)
	def get(self, request):
		"""
			Return the name of Reviewer and there corresponding details.
			query -- Please provide search keywords
		"""
		# return Response({"response" : "<h1>success</h1>"})
		self.query = request.GET.get('query')

		if self.query is None:
			raise exceptions.ValidationError(
				{'Error': 'Only allowed parameter is query. For example: "/scopus/?query=something"'})

		self.query = "query=TITLE-ABS-KEY(" + self.query + ")"
		article_list, err = self.findByTitleAbsKey()
		if err != None:
			return Response({'Error' : err})

		sys.stdout.flush()
		self.startTime = time()
		self.searchResult = {'searchResult': []}
		logging.debug("-----------------------------------------------------------------------------")
		logging.debug("                      Start Time : {}".format(date.today()))
		logging.debug("-----------------------------------------------------------------------------")
		isNext = True

		for eachArt in article_list:
			abs_link = eachArt.get('prism:url')
			if abs_link is None:
				print("Info: prism:url didn't found.")
				continue

			t = threading.Thread(target=self.call_process, args=(abs_link, eachArt))
			t.start()
			# isNext = self.call_process(abs_link, eachArt)
			# if isNext is False: break
		while True:
			if(len(self.searchResult['searchResult']) > 6):
				break
			# print("len : %d" % len(self.searchResult['searchResult']))

		time_taken = round(time() - self.startTime, 2)
		hours, rest = divmod(time_taken, 3600)

		if len(self.searchResult['searchResult']) > 0:
			self.searchResult['processTime'] = '%d minutes, %d second' % divmod(rest, 60)
			self.searchResult['searchItem'] = len(self.searchResult['searchResult'])
			return Response(self.searchResult)
		else:
			return Response({
				'Info': 'No result found',
				'processTime': '%d minutes, %d second' % divmod(rest, 60),
			})

	def call_process(self, abs_link, eachArt):
		self.parseURL(isAbs=True)
		logging.debug("(Second Search) Abstract Url %s?APIKey=%s&HTTPAccept=%s" % (abs_link, self.headers['X-ELS-APIKey'],
																		   self.headers['accept']))
		eachArticleInfo = self.req(abs_link, err_message="Abstract Url Exception: [%s] !\n" % (abs_link))

		if eachArticleInfo.get('abstracts-retrieval-response') is None or eachArticleInfo.get(\
				'abstracts-retrieval-response').get('authors') is None:
			print('Error: Authors not found. Please check your VPN running status.')
			return False
		if eachArticleInfo.get('abstracts-retrieval-response').get('language').get('@xml:lang') != 'eng':
			return False

		self.lang = 'English'
		scopus_abs_link = None
		for sco_lnk in eachArt.get('link'):
			if re.search(r"record\.uri", sco_lnk['@href']):
				scopus_abs_link = sco_lnk['@href']
				re.sub(r" ", "", scopus_abs_link)
				break

		auDetailList = eachArticleInfo['abstracts-retrieval-response']['authors']['author']

		for eachAUDetails in auDetailList:
			scopus_link = None
			documentInFiveYear = documentInTenYear = 0
			expertiseArea = []

			logging.debug("(Third Search) Authors Details Url : %s?APIKey=%s&HTTPAccept=%s" % (eachAUDetails[
																								'author-url'],
																				   self.headers['X-ELS-APIKey'], self.headers['accept']))

			au_data = self.req(eachAUDetails['author-url'], err_message="Link [%s] Request error!\n" % (eachAUDetails['author-url']))
			eachAUDetailsData = au_data['author-retrieval-response'][0]

			if eachAUDetailsData['coredata'].get('document-count') is None:
				continue
			if int(eachAUDetailsData['coredata']['document-count']) >= 75:
				continue
			for sa in eachAUDetailsData['subject-areas']['subject-area']:
				expertiseArea.append(sa.get('$'))
			afName = 'Not found'
			try:
				afName = eachAUDetailsData['author-profile']['affiliation-current']['affiliation']['ip-doc']['afdispname']
			except:
				logging.debug('Affiliation not found')

			instLink = 'Not found'
			try:
				instLink = eachAUDetailsData['author-profile']['affiliation-current']['affiliation']['ip-doc']['org-URL']
			except:
				logging.debug('Organization link not found')

			au_data_for_coauthor = None
			for lnk in eachAUDetailsData['coredata']['link']:
				if re.search(r"www.scopus.com/authid/", lnk['@href']):
					scopus_link = lnk['@href']
					re.sub(r" ", "", scopus_link)
				if re.search(r"http://api.elsevier.com/content/author/author_id/", lnk['@href']):
					au_data_for_coauthor = self.getAuData(lnk['@href'])
					documentInFiveYear, documentInTenYear = self.findDocumentInLastFiveYears(au_data_for_coauthor)

			if documentInFiveYear > 50 or documentInFiveYear < 5 or documentInTenYear < 10:
				continue

			if eachArticleInfo.get('abstracts-retrieval-response') is None or eachArticleInfo.get(
					'abstracts-retrieval-response').get('coredata') is None:
				continue
			else:
				document_title = eachArticleInfo.get('abstracts-retrieval-response').get('coredata').get('dc:title')

			if eachArticleInfo.get('abstracts-retrieval-response') is None or eachArticleInfo.get(
					'abstracts-retrieval-response').get('item') is None or eachArticleInfo.get(
					'abstracts-retrieval-response').get('item').get('bibrecord') is None or eachArticleInfo.get(
					'abstracts-retrieval-response').get('item').get('bibrecord').get('head') is None:
				document_abstract = 'N/A'
			else:
				document_abstract = eachArticleInfo.get('abstracts-retrieval-response').get('item').get('bibrecord').get(
				'head').get('abstracts')

			coAuthors = self.findCoAuthors(au_data_for_coauthor)

			searchDic = {'Author Name' : eachAUDetailsData['author-profile']['preferred-name']['given-name'] + " " +
											eachAUDetailsData['author-profile']['preferred-name']['surname'],
						 'Total Document in Complete tenure' : eachAUDetailsData['coredata']['document-count'],
						 'Author Scopus Link' : scopus_link,
						 'Publication count in last five year' : documentInFiveYear,
						 'Publication count in last ten year' : documentInTenYear,
						 'Title' : document_title,
						 'Abstract' : document_abstract,
						 'header link' : scopus_abs_link,
						 'Language' : self.lang,
						 'Subject Area' : expertiseArea,
						 'Affiliation' : afName,
						 'Org URL' : instLink,
						 'Co-authors' : coAuthors,
						 }
			# print(searchDic)
			self.searchResult['searchResult'].append(searchDic)
			if len(self.searchResult['searchResult']) > self.NO_OF_SEARCH_RESULT: return False
		if len(self.searchResult['searchResult']) > self.NO_OF_SEARCH_RESULT: return False

	def getAuData(self, auID):
		self.parseURL(isAbs=True)
		auID = re.sub(r".*/(\d+)$", r"\1", auID)

		# print("auID %s" % auID)
		url = 'http://api.elsevier.com/content/search/scopus?query=AU-ID(' + auID + ')'

		logging.debug(
			"(Fourth Search) Document In Last Five Year Url : %s&APIKey=%s&HTTPAccept=%s" % (url, self.headers[
				'X-ELS-APIKey'], self.headers['accept']))

		au_data = self.req(url, err_message="Link [%s] Request error (Author Page)!\n" % (url))
		return au_data

	def findCoAuthors(self, au_data):
		allCoAuth = []
		try:
			for each_entry in au_data['search-results']['entry']:
				abs_link = each_entry.get('prism:url')
				self.parseURL(isAbs=True)
				abs_link = abs_link + '?field=authors'
				authors = self.req(abs_link, err_message="Abstract Url Exception: [%s] !\n" % (abs_link))
				for eachAuthor in authors.get('abstracts-retrieval-response').get('authors').get('author'):
					allCoAuth.append('{0} {1}'.format(eachAuthor.get('ce:given-name'), eachAuthor.get('ce:surname')))
		except Exception as ex:
			print("Find co-authors error.")
		return ', '.join(set(allCoAuth))

	def findDocumentInLastFiveYears(self, au_data):
		doc_count = 0
		doc_count_ten = 0

		try:
			# au_info_request = requests.get(url, headers=self.headers)
			# au_data = json.loads(au_info_request.content.decode("utf-8"))
			# print("length of entry is : %s" % len(au_data['search-results']['entry']))
			current_year = date.today().year
			five_year = date.today().year - 4
			ten_year = date.today().year - 9
			# print("five_year %s" % five_year)
			for each_entry in au_data['search-results']['entry']:
				if each_entry.get('prism:coverDisplayDate') == None:
					continue
				year = each_entry['prism:coverDisplayDate']
				# print("before conversion year %s " %year)
				year = re.sub(r"^(?:(?!\d{4}).)*(\d{4}).*$", r"\1", year)
				# print("year: %s" %year)
				if int(year) <= current_year and int(year) >=five_year:
					doc_count = doc_count + 1
				if int(year) <= current_year and int(year) >=ten_year:
					doc_count_ten = doc_count_ten + 1
				# print("year %s " %year)
		except Exception as ex:
			print("Link [%s] Request error (Author Page)!\n %s " % (url, ex))
		return doc_count, doc_count_ten

	def findByTitleAbsKey(self):
		self.parseURL()
		url = 'http://api.elsevier.com/content/search/scopus?' + self.query
		# First Search : find no of search item
		page = self.req(url, err_message="Error : Request error [%s]! \n" % url)
		try:
			logging.debug("(First Search) ByTitleAbsKey Url : %s&APIKey=%s&view:COMPLETE&HTTPAccept=%s&count=10" % (url,
																											self.headers['X-ELS-APIKey'], self.headers['HTTPAccept']))
			# page_request = requests.get(url, headers = self.headers)
			# page_request = requests.get('http://api.elsevier.com/content/search/scopus?query=title-abs-key(micro)&APIKey=40ab7ae0b9e65f067cfe446e01585cc4&HTTPAccept=application/json&count=1')
			# page = json.loads(page_request.content.decode("utf-8"))
			if page['search-results']['opensearch:totalResults'] is '0':
				return None, 'Error : No document [%s] were found on scopus.' % self.query
		except Exception as ex:
			return None, "Error : Request error [%s]! \n %s " % (url, ex)

		# Get all searched Entry
		articles_list = page['search-results']['entry']
		return articles_list, None

	def parseURL(self, isAbs = False):
		if isAbs:
			self.headers = {
				'User-Agent': self.ua.random,
				settings.MY_API_KEY['key']: settings.MY_API_KEY['value'],
				'accept': 'application/json',
			}
		else:
			self.headers = {
				'User-Agent': self.ua.random,
				settings.MY_API_KEY['key']: settings.MY_API_KEY['value'],
				'HTTPAccept': 'application/json',
				'count': self.NO_OF_SEARCH_COUNT,
				'view': 'COMPLETE',
			}

	def req(self, link, err_message = '', isExit = False):
		eachArticleInfo = None
		try:
			link_request = requests.get(link, headers=self.headers, proxies = settings.PROXY)
			# link_request = requests.get(link, headers=self.headers)
			eachArticleInfo = json.loads(link_request.content.decode("utf-8"))
		except Exception as ex:
			print(err_message)

		return eachArticleInfo


class Login(APIView):
	permission_classes = (IsAuthenticated,)
	def get(self, request):
		return Response({'status':'200'})

class Home(APIView):
	renderer_classes = (StaticHTMLRenderer,)
	def get(self, request):
		return Response("""
		<html>
		<style type="text/css">body{background-color:white;}</style>
		<body>
		<a><img alt="" src="/static/logo/Springer-Nature.jpg" height="10px"></img></a>
		<h1>Reviewer Finder Tool</h1>
		</body>
		</html>
		""")
