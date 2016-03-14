import uuid
import json  # noqa
import logging
import httplib2

from oauth2client.service_account import ServiceAccountCredentials
from apiclient import discovery as apiclient_discovery, http as apiclient_http


log = logging.getLogger('storage')


class GoogleDrive(object):
    service_obj = dict()

    def __init__(self, credential_json, account_email, user_email):
        self.GOOGLE_SERVICE_ACCOUNT_JSON = credential_json
        self.GOOGLE_SERVICE_ACCOUNT_EMAIL = account_email
        self.GOOGLE_SERVICE_ACCOUNT_USER_EMAIL = user_email

    def _get_service(self):
        if self.service_obj:
            return self.service_obj

        credentials = ServiceAccountCredentials.from_json_keyfile_dict(
            json.loads(self.GOOGLE_SERVICE_ACCOUNT_JSON),
            scopes='https://www.googleapis.com/auth/drive',
        )

        http = httplib2.Http()
        delegated_credentials = credentials.create_delegated(self.GOOGLE_SERVICE_ACCOUNT_USER_EMAIL)
        http = delegated_credentials.authorize(http)

        self.service_obj = apiclient_discovery.build('drive', 'v3', http=http)

        return self.service_obj

    def get_files(self, query=None, **kw):
        log.debug('%s: trying to get files list')

        service = self._get_service()

        result = list()
        page_token = None
        while True:
            param = kw.copy()
            if page_token:
                param['pageToken'] = page_token
            if query:
                param['q'] = query

            l = service.files().list(**param).execute()
            result.extend(l.get('files'))
            page_token = l.get('nextPageToken')
            if page_token is None:
                break

        return result

    def _make_properties(self, properties):
        if not properties:
            properties = dict()

        properties['creator'] = 'site-shooter'

        return map(lambda x: dict(key=x[0], value=x[1]), properties.items())

    def upload(self, content, parent_ids=None, filename=None, description=None, mimetype='application/octet-stream', **options):
        if isinstance(content, file):
            media_body = apiclient_http.MediaInMemoryUpload(
                content,
                mimetype=mimetype,
                resumable=True,
            )
        else:
            media_body = apiclient_http.MediaInMemoryUpload(
                content,
                mimetype=mimetype,
                resumable=True,
            )

        body = dict(
            name=filename if filename else uuid.uuid1().hex,
            description=description if description else None,
            mimeType=mimetype,
            parents=list(),
            properties=self._make_properties(options.get('properties')),
        )

        if parent_ids:
            body['parents'] = parent_ids

        service = self._get_service()
        return service.files().create(body=body, media_body=media_body).execute()

    def mkdir(self, name, parent_ids=list(), description=None, **options):
        '''
        For detailed options, https://developers.google.com/drive/v2/reference/files/insert .
        '''

        body = dict(
            name=name,
            mimeType='application/vnd.google-apps.folder',
        )

        if parent_ids:
            body['parents'] = list(parent_ids)

        body.update(options)

        return self._get_service().files().create(body=body, fields='id').execute()
