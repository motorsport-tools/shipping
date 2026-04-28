 
 
 
"""Royal Mail Click and Drop carrier return services helper tests."""

import unittest
from unittest.mock import patch

from . import fixture
import logging
import karrio.sdk as karrio
import karrio.lib as lib
import karrio.core.models as models

logger = logging.getLogger(__name__)


class TestRoyalMailClickandDropReturnServices(unittest.TestCase):
    def setUp(self):
        self.maxDiff = None
        self.ReturnServicesRequest = fixture.ReturnServicesRequest

    def test_create_get_return_services_request(self):
        """Build the empty request payload required by the return services endpoint."""
        request = fixture.gateway.mapper.create_get_return_services_request(
            self.ReturnServicesRequest
        )

        print(f"Generated request: {request.serialize()}")
        self.assertEqual(request.serialize(), fixture.ReturnServicesRequest)

    def test_get_return_services(self):
        """Verify the proxy calls GET /returns/services."""
        with patch("karrio.mappers.royalmail_clickdrop.proxy.lib.request") as mock:
            mock.return_value = "{}"

            request = fixture.gateway.mapper.create_get_return_services_request(
                self.ReturnServicesRequest
            )
            fixture.gateway.proxy.get_return_services(request)

            print(f"Called URL: {mock.call_args[1]['url']}")
            self.assertEqual(
                mock.call_args[1]["url"],
                f"{fixture.gateway.settings.server_url}/returns/services",
            )

    def test_parse_get_return_services_response(self):
        """Parse a successful return services response into the expected native schema object."""
        with patch("karrio.mappers.royalmail_clickdrop.proxy.lib.request") as mock:
            mock.return_value = fixture.ReturnServicesResponse

            request = fixture.gateway.mapper.create_get_return_services_request(
                self.ReturnServicesRequest
            )
            response = fixture.gateway.proxy.get_return_services(request)
            parsed_response = list(
                fixture.gateway.mapper.parse_get_return_services_response(response)
            )

            print(f"Parsed response: {lib.to_dict(parsed_response)}")
            self.assertListEqual(
                lib.to_dict(parsed_response),
                fixture.ParsedReturnServicesResponse,
            )

    def test_parse_error_response(self):
        """Normalize Royal Mail return services errors into Karrio message objects."""
        with patch("karrio.mappers.royalmail_clickdrop.proxy.lib.request") as mock:
            mock.return_value = fixture.ReturnServicesErrorResponse

            request = fixture.gateway.mapper.create_get_return_services_request(
                self.ReturnServicesRequest
            )
            response = fixture.gateway.proxy.get_return_services(request)
            parsed_response = list(
                fixture.gateway.mapper.parse_get_return_services_response(response)
            )

            print(f"Error response: {lib.to_dict(parsed_response)}")
            self.assertListEqual(
                lib.to_dict(parsed_response),
                fixture.ParsedReturnServicesErrorResponse,
            )

