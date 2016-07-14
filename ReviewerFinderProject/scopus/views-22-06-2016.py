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
import sys
# from rest_framework.authentication import BasicAuthentication

from pprint import pprint

# from rest_framework.response import Response
# from rest_framework.decorators import api_view, authentication_classes, renderer_classes


class ScopusView(APIView):
	# Below line commented for testing purpose. Once uncommented, only database user can access it.
	# authentication_classes = (BasicAuthentication,)
	# permission_classes = (IsAuthenticated,)
	def __init__(self):
		self.ua = UserAgent()

	renderer_classes = (JSONRenderer,)
	def get(self, request):
		"""
			Return the name of Reviewer and there corresponding details.
			query -- Please provide search keywords
		"""
		# return Response({"response" : "<h1>success</h1>"})
		self.query = request.GET.get('query')
		# self.query = request.query_params.get('query')

		if self.query is None:
			raise exceptions.ValidationError(
				{'Error': 'Only allowed parameter is query. For example: "/scopus/?query=something"'})
		# query = request.query_params['query']
		article_list, err = self.findByTitleAbsKey()
		if err != None:
			return Response({'Error' : err})
		# find Article Info
		# return Response(article_list)
		sys.stdout.flush()
		self.startTime = time()
		findArticleInfo = self.findByArticleTitle(article_list)

		searchResult = {'searchResult': []}
		for eachArticleInfo in findArticleInfo:
			# Get all authors details
			if eachArticleInfo.get('abstracts-retrieval-response') is None or eachArticleInfo.get(\
					'abstracts-retrieval-response').get('authors') is None:
				return Response({'Error' : 'Authors not found. Please check your VPN running status.'})
			auDetailList = self.findAuthorsDetails(eachArticleInfo['abstracts-retrieval-response']['authors'])
			# print(auDetailList)
			# return Response({'searchResult' : auDetailList})
			for eachAUDetails in auDetailList:
				# print("Given Name %s" % eachAUDetails.get('given-name'))
				scopus_link = None
				documentInFiveYear = 0;
				documentInTenYear = 0;
				if eachAUDetails['coredata'].get('document-count') is None:
					continue
				if int(eachAUDetails['coredata']['document-count']) > 75:
					continue

				for lnk in eachAUDetails['coredata']['link']:
					if re.search(r"www.scopus.com/authid/", lnk['@href']):
						scopus_link = lnk['@href']
						re.sub(r" ", "", scopus_link)
					if re.search(r"http://api.elsevier.com/content/author/author_id/", lnk['@href']):
						documentInFiveYear, documentInTenYear = self.findDocumentInLastFiveYears(lnk['@href'])

				# if documentInFiveYear > 50 or documentInFiveYear < 5 or documentInTenYear < 10:
				# if documentInFiveYear > 50:
				if documentInFiveYear > 50 or documentInFiveYear < 5:
					continue
				# print(eachArticleInfo)
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
				searchDic = {'Author Name' : eachAUDetails['author-profile']['preferred-name']['given-name'] + " " +
												eachAUDetails['author-profile']['preferred-name']['surname'],
							 'Total Document in Complete tenure' : eachAUDetails['coredata']['document-count'],
							 'Author Scopus Link' : scopus_link,
							 'Publication count in last five year' : documentInFiveYear,
							 # 'Publication count in last ten year' : documentInTenYear,
							 'Title' : document_title,
							 'Abstract' : document_abstract,
							 }
				# print(searchDic)
				searchResult['searchResult'].append(searchDic)
				if len(searchResult['searchResult']) > 6: break
			if len(searchResult['searchResult']) > 6: break
		# print(auDetailList)
		# print(au_data['author-retrieval-response'][0]['coredata']['document-count'])
		# findAllURL(article_list)
		endTime = time() - self.startTime;
		endTime = round(endTime / 60, 2);
		if len(searchResult['searchResult']) > 0:
			searchResult['processTime'] = '%f min' % endTime;
			return Response(searchResult)
		else:
			return Response({
				'Info' : 'No result found',
				'processTime' : '%f min' % endTime,
			})

	def findDocumentInLastFiveYears(self, link):
		self.parseURL(isAbs=True)
		doc_count = 0
		doc_count_ten = 0
		auID = link
		auID = re.sub(r".*/(\d+)$", r"\1", auID)
		# print("auID %s" % auID)
		url = 'http://api.elsevier.com/content/search/scopus?query=AU-ID(' + auID + ')'
		try:
			print("(Fourth Search) Document In Last Five Year Url : %s&X-ELS-APIKey=%s&accept=%s" % (url, self.headers[
				'X-ELS-APIKey'], self.headers['accept']))
			au_info_request = requests.get(url, headers=self.headers)
			au_data = json.loads(au_info_request.content.decode("utf-8"))
			# print("length of entry is : %s" % len(au_data['search-results']['entry']))
			current_year = date.today().year
			five_year = date.today().year - 4
			ten_year = date.today().year - 9
			# print("five_year %s" % five_year)
			for each_entry in au_data['search-results']['entry']:
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

	def findAuthorsDetails(self, auInfoDic):
		auDataList = []
		for au_details in auInfoDic['author']:
			self.parseURL(isAbs=True)
			try:
				print("(Third Search) Authors Details Url : %s?X-ELS-APIKey=%s&accept=%s" % (au_details['author-url'], self.headers['X-ELS-APIKey'], self.headers['accept']))
				au_info_request = requests.get(au_details['author-url'], headers=self.headers)
				# print("Response: %s" % au_info_request.content.decode("utf-8"))
				au_data = json.loads(au_info_request.content.decode("utf-8"))
				# print(au_data['author-retrieval-response'][0]['coredata']['document-count'])
				auDataList.append(au_data['author-retrieval-response'][0])

			except Exception as ex:
				print("Link [%s] Request error!\n %s " % (au_details['author-url'], ex))

		return (auDataList)

	def findByArticleTitle(self, ArtList):
		articleInfo = [] # should have list of hash

		for eachArt in ArtList:
			links = eachArt.get('link')
			if links is None:
				return {"Error : " : "prism:issueIdentifier is empty."}

			for eachLink in links:
				if re.search(r"http://api.elsevier.com/content/abstract/scopus_id/", eachLink.get("@href")):
					abs_link = eachLink.get("@href")
					break
			# print("Type of eachArt : %s " % type(eachArt))
			# print("eachArt : %s " % eachArt)
			self.parseURL(isAbs=True)
			try:
				print("(Second Search) Abstract Url %s?X-ELS-APIKey=%s&accept=%s" % (abs_link, self.headers['X-ELS-APIKey'],
																					 self.headers['accept']))
				link_request = requests.get(abs_link, headers=self.headers)
				# print(link_request.content.decode("utf-8"))
				link_data = json.loads(link_request.content.decode("utf-8"))
				articleInfo.append(link_data)
			except Exception as ex:
				print("Abstract Url Exception: [%s] !\n %s " % (abs_link, ex))
			# break
			#Start to removing break from here
		return articleInfo

	def findByTitleAbsKey(self):
		self.parseURL()
		url = 'http://api.elsevier.com/content/search/scopus?' + self.query
		# First Search : find no of search item
		try:
			print("(First Search) ByTitleAbsKey Url : %s&X-ELS-APIKey=%s&view:COMPLETE&HTTPAcceptaccept=%s" % (url,
																											   self.headers['X-ELS-APIKey'], self.headers['HTTPAccept']))
			page_request = requests.get(url, headers = self.headers)
			# page_request = requests.get('http://api.elsevier.com/content/search/scopus?query=title-abs-key(micro)&APIKey=40ab7ae0b9e65f067cfe446e01585cc4&HTTPAccept=application/json&count=1')
			page = json.loads(page_request.content.decode("utf-8"))
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
				'count': '5',
				'view': 'COMPLETE',
			}
		self.query = "query=title-abs-key(" + self.query + ")"

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
