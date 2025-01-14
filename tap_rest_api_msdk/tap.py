"""rest-api tap class."""

import requests
from typing import List

from genson import SchemaBuilder
from singer_sdk import Tap, Stream
from singer_sdk import typing as th
from singer_sdk.helpers.jsonpath import extract_jsonpath

from tap_rest_api_msdk.streams import DynamicStream
from tap_rest_api_msdk.utils import flatten_json


class TapRestApiMsdk(Tap):
    """rest-api tap class."""
    name = "tap-rest-api-msdk"

    config_jsonschema = th.PropertiesList(
        th.Property("api_url", th.StringType, required=True,
                    description="the base url/endpoint for the desired api"),
        # th.Property("auth_method", th.StringType, default='no_auth', required=False),
        # th.Property("auth_token", th.StringType, required=False),
        th.Property('name', th.StringType, required=True,
                    description="name of the stream"),
        th.Property('path', th.StringType, default="", required=False,
                    description="the path appeneded to the `api_url`."),
        th.Property('params', th.ObjectType(), required=False,
                    description="an object of objects that provide the `params` in a `requests.get` method."),
        th.Property('headers', th.ObjectType(), required=False,
                    description="an object of headers to pass into the api calls."),
        th.Property("records_path", th.StringType, default="$[*]", required=False,
                    description="a jsonpath string representing the path in the requests response that contains the "
                                "records to process. Defaults to `$[*]`."),
        th.Property("next_page_token_path", th.StringType, default="$.next_page", required=False,
                    description="a jsonpath string representing the path to the 'next page' token. "
                                "Defaults to `$.next_page`"),
        th.Property('primary_keys', th.ArrayType(th.StringType), required=True,
                    description="a list of the json keys of the primary key for the stream."),
        th.Property('replication_key', th.StringType, required=False,
                    description="the json key of the replication key. Note that this should be an incrementing "
                                "integer or datetime object."),
        th.Property('except_keys', th.ArrayType(th.StringType), default=[], required=False,
                    description="This tap automatically flattens the entire json structure and builds keys based on "
                                "the corresponding paths.; Keys, whether composite or otherwise, listed in this "
                                "dictionary will not be recursively flattened, but instead their values will be; "
                                "turned into a json string and processed in that format. This is also automatically "
                                "done for any lists within the records; therefore,; records are not duplicated for "
                                "each item in lists."),
        th.Property('num_inference_records', th.NumberType, default=50, required=False,
                    description="number of records used to infer the stream's schema. Defaults to 50."),
    ).to_dict()

    def discover_streams(self) -> List[Stream]:
        """Return a list of discovered streams."""
        return [
            DynamicStream(
                tap=self,
                name=self.config['name'],
                path=self.config['path'],
                params=self.config.get('params'),
                headers=self.config.get('headers'),
                records_path=self.config['records_path'],
                next_page_token_path=self.config['next_page_token_path'],
                primary_keys=self.config['primary_keys'],
                replication_key=self.config.get('replication_key'),
                except_keys=self.config.get('except_keys'),
                schema=self.get_schema(
                    self.config['records_path'],
                    self.config.get('except_keys'),
                    self.config.get('num_inference_records'),
                    self.config['path'],
                    self.config.get('params'),
                    self.config.get('headers'),
                )
            )
        ]

    def get_schema(self, records_path, except_keys, inference_records, path, params, headers) -> dict:
        """Infer schema from the first records returned by api. Creates a Stream object."""

        # todo: this request format is not very robust
        r = requests.get(self.config['api_url'] + path, params=params, headers=headers)
        if r.ok:
            records = extract_jsonpath(records_path, input=r.json())
        else:
            raise ValueError(r.text)

        builder = SchemaBuilder()
        builder.add_schema(th.PropertiesList().to_dict())
        for i, record in enumerate(records):
            if type(record) is not dict:
                raise ValueError("Input must be a dict object.")

            flat_record = flatten_json(record, except_keys)
            builder.add_object(flat_record)

            if i >= inference_records:
                break

        self.logger.debug(f"{builder.to_json(indent=2)}")
        return builder.to_schema()
