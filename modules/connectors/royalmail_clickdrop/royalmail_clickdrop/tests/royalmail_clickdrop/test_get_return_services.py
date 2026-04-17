"""Royal Mail Click and Drop carrier return services helper tests."""

import unittest
from unittest.mock import patch

import karrio.lib as lib

from .fixture import gateway


class TestRoyalMailClickandDropReturnServices(unittest.TestCase):
    def setUp(self):
        self.maxDiff = None
        self.ReturnServicesRequest = {}

    def test_create_get_return_services_request(self):
        request = gateway.mapper.create_get_return_services_request(
            self.ReturnServicesRequest
        )

        print(f"Generated request: {request.serialize()}")
        self.assertEqual(request.serialize(), ReturnServicesRequest)

    def test_get_return_services(self):
        with patch("karrio.mappers.royalmail_clickdrop.proxy.lib.request") as mock:
            mock.return_value = "{}"

            request = gateway.mapper.create_get_return_services_request(
                self.ReturnServicesRequest
            )
            gateway.proxy.get_return_services(request)

            print(f"Called URL: {mock.call_args[1]['url']}")
            self.assertEqual(
                mock.call_args[1]["url"],
                f"{gateway.settings.server_url}/returns/services",
            )

    def test_parse_get_return_services_response(self):
        with patch("karrio.mappers.royalmail_clickdrop.proxy.lib.request") as mock:
            mock.return_value = ReturnServicesResponse

            request = gateway.mapper.create_get_return_services_request(
                self.ReturnServicesRequest
            )
            response = gateway.proxy.get_return_services(request)
            parsed_response = list(
                gateway.mapper.parse_get_return_services_response(response)
            )

            print(f"Parsed response: {lib.to_dict(parsed_response)}")
            self.assertListEqual(
                lib.to_dict(parsed_response),
                ParsedReturnServicesResponse,
            )

    def test_parse_error_response(self):
        with patch("karrio.mappers.royalmail_clickdrop.proxy.lib.request") as mock:
            mock.return_value = ReturnServicesErrorResponse

            request = gateway.mapper.create_get_return_services_request(
                self.ReturnServicesRequest
            )
            response = gateway.proxy.get_return_services(request)
            parsed_response = list(
                gateway.mapper.parse_get_return_services_response(response)
            )

            print(f"Error response: {lib.to_dict(parsed_response)}")
            self.assertListEqual(
                lib.to_dict(parsed_response),
                ParsedErrorResponse,
            )


if __name__ == "__main__":
    unittest.main()


ReturnServicesRequest = {}

ReturnServicesResponse = """{
  "services": [
    {
      "carrierGuid": "carrier-guid-1",
      "carrierServiceGuid": "service-guid-1",
      "serviceName": "Tracked Returns 48",
      "serviceCode": "TSS"
    }
  ]
}"""

ReturnServicesErrorResponse = """{
  "code": "Forbidden",
  "message": "Not authorised to view return services"
}"""

ParsedReturnServicesResponse = [
    {
        "services": [
            {
                "carrierGuid": "carrier-guid-1",
                "carrierServiceGuid": "service-guid-1",
                "serviceName": "Tracked Returns 48",
                "serviceCode": "TSS",
            }
        ]
    },
    [],
]

ParsedErrorResponse = [
    None,
    [
        {
            "carrier_id": "royalmail_clickdrop",
            "carrier_name": "royalmail_clickdrop",
            "code": "Forbidden",
            "message": "Not authorised to view return services",
            "details": {
                "operation": "get_return_services",
            },
        }
    ],
]