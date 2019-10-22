from typing import Any
from typing import Dict
from typing import List
from typing import Optional

import requests
from lxml import etree
from requests_toolbelt import SSLAdapter

from .list import _List
from .soap import Soap
from .version import __version__

# import defusedxml.ElementTree as etree


class Site:
    """Connect to SharePoint Site
    """

    def __init__(
        self,
        site_url: str,
        auth: Optional[Any] = None,
        authcookie: Optional[requests.cookies.RequestsCookieJar] = None,
        verify_ssl: bool = True,
        ssl_version: Optional[float] = None,
        huge_tree: bool = False,
        timeout: Optional[int] = None,
    ):
        self.site_url = site_url
        self._verify_ssl = verify_ssl

        self._session = requests.Session()
        if ssl_version is not None:
            self._session.mount("https://", SSLAdapter(ssl_version))

        self._session.headers.update({"user-agent": "shareplum/%s" % __version__})

        if authcookie is not None:
            self._session.cookies = authcookie
        else:
            self._session.auth = auth

        self.huge_tree = huge_tree

        self.timeout = timeout

        self.last_request: Optional[str] = None

        self._services_url: Dict[str, str] = {
            "Alerts": "/_vti_bin/Alerts.asmx",
            "Authentication": "/_vti_bin/Authentication.asmx",
            "Copy": "/_vti_bin/Copy.asmx",
            "Dws": "/_vti_bin/Dws.asmx",
            "Forms": "/_vti_bin/Forms.asmx",
            "Imaging": "/_vti_bin/Imaging.asmx",
            "DspSts": "/_vti_bin/DspSts.asmx",
            "Lists": "/_vti_bin/lists.asmx",
            "Meetings": "/_vti_bin/Meetings.asmx",
            "People": "/_vti_bin/People.asmx",
            "Permissions": "/_vti_bin/Permissions.asmx",
            "SiteData": "/_vti_bin/SiteData.asmx",
            "Sites": "/_vti_bin/Sites.asmx",
            "Search": "/_vti_bin/Search.asmx",
            "UserGroup": "/_vti_bin/usergroup.asmx",
            "Versions": "/_vti_bin/Versions.asmx",
            "Views": "/_vti_bin/Views.asmx",
            "WebPartPages": "/_vti_bin/WebPartPages.asmx",
            "Webs": "/_vti_bin/Webs.asmx",
        }

        self.users = self.get_users()

    def _url(self, service: str) -> str:
        """Full SharePoint Service URL"""
        return "".join([self.site_url, self._services_url[service]])

    def _headers(self, soap_action: str) -> Dict[str, str]:
        headers = {
            "Content-Type": "text/xml; charset=UTF-8",
            "SOAPAction": "http://schemas.microsoft.com/sharepoint/soap/" + soap_action,
        }
        return headers

    # This is part of List but seems awkward under the List Method
    def add_list(self, list_name, description, template_id):
        """Create a new List
           Provide: List Name, List Description, and List Template
           Templates Include:
               Announcements
               Contacts
               Custom List
               Custom List in Datasheet View
               DataSources
               Discussion Board
               Document Library
               Events
               Form Library
               Issues
               Links
               Picture Library
               Survey
               Tasks
        """
        template_ids = {
            "Announcements": "104",
            "Contacts": "105",
            "Custom List": "100",
            "Custom List in Datasheet View": "120",
            "DataSources": "110",
            "Discussion Board": "108",
            "Document Library": "101",
            "Events": "106",
            "Form Library": "115",
            "Issues": "1100",
            "Links": "103",
            "Picture Library": "109",
            "Survey": "102",
            "Tasks": "107",
        }

        # Let's automatically convert the different
        # ways we can select the template_id
        if type(template_id) == int:
            template_id = str(template_id)
        elif type(template_id) == str:
            if template_id.isdigit():
                pass
            else:
                template_id = template_ids[template_id]

        # Build Request
        soap_request = Soap("AddList")
        soap_request.add_parameter("listName", list_name)
        soap_request.add_parameter("description", description)
        soap_request.add_parameter("templateID", template_id)
        self.last_request = str(soap_request)

        # Send Request
        response = self._session.post(
            url=self._url("Lists"),
            headers=self._headers("AddList"),
            data=str(soap_request),
            verify=self._verify_ssl,
            timeout=self.timeout,
        )

        # Parse Request
        print(response)
        if response == 200:
            return response.text
        else:
            return response

    def delete_list(self, list_name: str) -> Optional[str]:
        """Delete a List with given name"""

        # Build Request
        soap_request = Soap("DeleteList")
        soap_request.add_parameter("listName", list_name)
        self.last_request = str(soap_request)

        # Send Request
        response = self._session.post(
            url=self._url("Lists"),
            headers=self._headers("DeleteList"),
            data=str(soap_request).encode("utf-8"),
            verify=self._verify_ssl,
            timeout=self.timeout,
        )

        # Parse Request
        if response == 200:
            return response.text
        else:
            response.raise_for_status()
            raise RuntimeError(f"Response code: {response.status_code}, response: {response.text}")

    def get_list_collection(self) -> Optional[List[Dict[str, str]]]:
        """Returns List information for current Site"""
        # Build Request
        soap_request = Soap("GetListCollection")
        self.last_request = str(soap_request)

        # Send Request
        response = self._session.post(
            url=self._url("SiteData"),
            headers=self._headers("GetListCollection"),
            data=str(soap_request).encode("utf-8"),
            verify=self._verify_ssl,
            timeout=self.timeout,
        )

        # Parse Response
        if response.status_code == 200:
            envelope = etree.fromstring(response.text.encode("utf-8"), parser=etree.XMLParser(huge_tree=self.huge_tree))
            # TODO: Fix this
            lists = envelope[0][0][1]
            data = []
            for _list in lists:
                _list_data = {}
                for item in _list:
                    key = item.tag.replace("{http://schemas.microsoft.com/sharepoint/soap/}", "")
                    value = item.text
                    _list_data[key] = value
                data.append(_list_data)

            return data
        else:
            response.raise_for_status()
            raise RuntimeError(f"Response code: {response.status_code}, response: {response.text}")

    def get_users(self, rowlimit: int = 0) -> Optional[Dict[str, Dict[str, str]]]:
        """Get Items from current list
           rowlimit defaulted to 0 (no limit)
        """

        # Build Request
        soap_request = Soap("GetListItems")
        soap_request.add_parameter("listName", "UserInfo")

        # Set Row Limit
        soap_request.add_parameter("rowLimit", str(rowlimit))
        self.last_request = str(soap_request)

        # Send Request
        response = self._session.post(
            url=self._url("Lists"),
            headers=self._headers("GetListItems"),
            data=str(soap_request).encode("utf-8"),
            verify=self._verify_ssl,
            timeout=self.timeout,
        )

        # Parse Response
        if response.status_code != 200:
            raise ConnectionError("GetUsers GetListItems request failed")
        try:
            envelope = etree.fromstring(response.text.encode("utf-8"), parser=etree.XMLParser(huge_tree=self.huge_tree))
        except Exception as e:
            raise ConnectionError(f"GetUsers GetListItems response failed to parse correctly: {e}")
        # TODO: Fix me with XPath
        listitems = envelope[0][0][0][0][0]
        data = []
        for row in listitems:
            # Strip the 'ows_' from the beginning with key[4:]
            data.append({key[4:]: value for (key, value) in row.items() if key[4:]})

        return {
            "py": {i["ImnName"]: i["ID"] + ";#" + i["ImnName"] for i in data},
            "sp": {i["ID"] + ";#" + i["ImnName"]: i["ImnName"] for i in data},
        }

    # SharePoint Method Objects
    def list(self, list_name: str, exclude_hidden_fields: bool = False) -> _List:
        """Sharepoint Lists Web Service
           Microsoft Developer Network:
           The Lists Web service provides methods for working
           with SharePoint lists, content types, list items, and files.
        """
        return _List(
            self._session,
            list_name,
            self._url,
            self._verify_ssl,
            self.users,
            self.huge_tree,
            self.timeout,
            exclude_hidden_fields=exclude_hidden_fields,
        )
