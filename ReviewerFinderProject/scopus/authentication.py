import base64
from rest_framework.authentication import BasicAuthentication
from rest_framework import exceptions
from django.conf import settings

class CustomAuthentication(BasicAuthentication):
	def get_authorization_header(self, request):
		"""
		Return request's 'Authorization:' header, as a bytestring.

		Hide some test client ickyness where the header can be unicode.
		"""
		auth = request.META.get('HTTP_AUTHORIZATION', b'')
		if isinstance(auth, type('')):
			# Work around django test client oddness
			auth = auth.encode('iso-8859-1')
		return auth

	def authenticate(self, request):
		auth = self.get_authorization_header(request).split()
		if not auth or auth[0].lower() != b'basic':
			msg = ('Invalid credentials: No credentials provided.')
			raise exceptions.AuthenticationFailed(msg)

		if len(auth) == 1:
			msg = ('Invalid basic header. No credentials provided.')
			raise exceptions.AuthenticationFailed(msg)
		elif len(auth) > 2:
			msg = ('Invalid basic header. Credentials string should not contain spaces.')
			raise exceptions.AuthenticationFailed(msg)

		try:
			decoded_auth = base64.b64decode(auth[1]).decode('iso-8859-1')
			auth_parts = decoded_auth.partition(':')
		except (TypeError, UnicodeDecodeError):
			msg = ('Invalid basic header. Credentials not correctly base64 encoded.')
			raise exceptions.AuthenticationFailed(msg)

		userName, password = auth_parts[0], auth_parts[2]
		# print("User Name is [%s] and Password is [%s]" % (userName, password))
		# return self.authenticate_credentials(userid, password)

		if not (userName == settings.USER and password == settings.PASS):
			raise exceptions.AuthenticationFailed('No such user')
