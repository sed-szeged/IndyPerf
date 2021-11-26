from asynctest import TestCase as AsyncTestCase
from asynctest import mock as async_mock

from ....admin.request_context import AdminRequestContext
from ....core.in_memory import InMemoryProfile
from ....indy.issuer import IndyIssuer
from ....ledger.base import BaseLedger
from ....storage.base import BaseStorage
from ....tails.base import BaseTailsServer

from .. import routes as test_module
from ....connections.models.conn_record import ConnRecord


SCHEMA_ID = "WgWxqztrNooG92RXvxSTWv:2:schema_name:1.0"
CRED_DEF_ID = "WgWxqztrNooG92RXvxSTWv:3:CL:20:tag"


class TestCredentialDefinitionRoutes(AsyncTestCase):
    def setUp(self):
        self.session_inject = {}
        self.profile = InMemoryProfile.test_profile()
        self.profile_injector = self.profile.context.injector

        self.ledger = async_mock.create_autospec(BaseLedger)
        self.ledger.__aenter__ = async_mock.CoroutineMock(return_value=self.ledger)
        self.ledger.create_and_send_credential_definition = async_mock.CoroutineMock(
            return_value=(
                CRED_DEF_ID,
                {"cred": "def", "signed_txn": "..."},
                True,
            )
        )
        self.ledger.get_credential_definition = async_mock.CoroutineMock(
            return_value={"cred": "def", "signed_txn": "..."}
        )
        self.profile_injector.bind_instance(BaseLedger, self.ledger)

        self.issuer = async_mock.create_autospec(IndyIssuer)
        self.profile_injector.bind_instance(IndyIssuer, self.issuer)

        self.storage = async_mock.create_autospec(BaseStorage)
        self.storage.find_all_records = async_mock.CoroutineMock(
            return_value=[async_mock.MagicMock(value=CRED_DEF_ID)]
        )
        self.session_inject[BaseStorage] = self.storage

        self.context = AdminRequestContext.test_context(
            self.session_inject, profile=self.profile
        )
        self.request_dict = {
            "context": self.context,
            "outbound_message_router": async_mock.CoroutineMock(),
        }
        self.request = async_mock.MagicMock(
            app={},
            match_info={},
            query={},
            __getitem__=lambda _, k: self.request_dict[k],
        )

    async def test_send_credential_definition(self):
        self.request.json = async_mock.CoroutineMock(
            return_value={
                "schema_id": "WgWxqztrNooG92RXvxSTWv:2:schema_name:1.0",
                "support_revocation": False,
                "tag": "tag",
            }
        )

        self.request.query = {"create_transaction_for_endorser": "false"}

        with async_mock.patch.object(test_module.web, "json_response") as mock_response:
            result = (
                await test_module.credential_definitions_send_credential_definition(
                    self.request
                )
            )
            assert result == mock_response.return_value
            mock_response.assert_called_once_with(
                {"sent": {"credential_definition_id": CRED_DEF_ID}}
            )

    async def test_send_credential_definition_revoc(self):
        self.request.json = async_mock.CoroutineMock(
            return_value={
                "schema_id": "WgWxqztrNooG92RXvxSTWv:2:schema_name:1.0",
                "support_revocation": True,
                "tag": "tag",
            }
        )

        self.request.query = {"create_transaction_for_endorser": "false"}

        self.context.profile.settings.set_value(
            "tails_server_base_url", "http://1.2.3.4:8222"
        )

        mock_tails_server = async_mock.MagicMock(
            upload_tails_file=async_mock.CoroutineMock(return_value=(True, None))
        )
        self.profile_injector.bind_instance(BaseTailsServer, mock_tails_server)

        with async_mock.patch.object(
            test_module, "IndyRevocation", async_mock.MagicMock()
        ) as test_indy_revoc, async_mock.patch.object(
            test_module.web, "json_response", async_mock.MagicMock()
        ) as mock_response:
            test_indy_revoc.return_value = async_mock.MagicMock(
                init_issuer_registry=async_mock.CoroutineMock(
                    return_value=async_mock.MagicMock(
                        set_tails_file_public_uri=async_mock.CoroutineMock(),
                        generate_registry=async_mock.CoroutineMock(),
                        send_def=async_mock.CoroutineMock(),
                        send_entry=async_mock.CoroutineMock(),
                        stage_pending_registry=async_mock.CoroutineMock(),
                    )
                )
            )

            await test_module.credential_definitions_send_credential_definition(
                self.request
            )
            mock_response.assert_called_once_with(
                {"sent": {"credential_definition_id": CRED_DEF_ID}}
            )

    async def test_send_credential_definition_revoc_no_tails_server_x(self):
        self.request.json = async_mock.CoroutineMock(
            return_value={
                "schema_id": "WgWxqztrNooG92RXvxSTWv:2:schema_name:1.0",
                "support_revocation": True,
                "tag": "tag",
            }
        )

        self.request.query = {"create_transaction_for_endorser": "false"}

        with self.assertRaises(test_module.web.HTTPBadRequest):
            await test_module.credential_definitions_send_credential_definition(
                self.request
            )

    async def test_send_credential_definition_revoc_no_support_x(self):
        self.request.json = async_mock.CoroutineMock(
            return_value={
                "schema_id": "WgWxqztrNooG92RXvxSTWv:2:schema_name:1.0",
                "support_revocation": True,
                "tag": "tag",
            }
        )

        self.request.query = {"create_transaction_for_endorser": "false"}

        self.context.profile.settings.set_value(
            "tails_server_base_url", "http://1.2.3.4:8222"
        )

        with async_mock.patch.object(
            test_module, "IndyRevocation", async_mock.MagicMock()
        ) as test_indy_revoc:
            test_indy_revoc.return_value = async_mock.MagicMock(
                init_issuer_registry=async_mock.CoroutineMock(
                    side_effect=test_module.RevocationNotSupportedError("nope")
                )
            )
            with self.assertRaises(test_module.web.HTTPBadRequest):
                await test_module.credential_definitions_send_credential_definition(
                    self.request
                )

    async def test_send_credential_definition_revoc_upload_x(self):
        self.request.json = async_mock.CoroutineMock(
            return_value={
                "schema_id": "WgWxqztrNooG92RXvxSTWv:2:schema_name:1.0",
                "support_revocation": True,
                "tag": "tag",
            }
        )

        self.request.query = {"create_transaction_for_endorser": "false"}

        self.context.profile.settings.set_value(
            "tails_server_base_url", "http://1.2.3.4:8222"
        )

        mock_tails_server = async_mock.MagicMock(
            upload_tails_file=async_mock.CoroutineMock(
                return_value=(False, "Down for maintenance")
            )
        )
        self.profile_injector.bind_instance(BaseTailsServer, mock_tails_server)

        with async_mock.patch.object(
            test_module, "IndyRevocation", async_mock.MagicMock()
        ) as test_indy_revoc:
            test_indy_revoc.return_value = async_mock.MagicMock(
                init_issuer_registry=async_mock.CoroutineMock(
                    return_value=async_mock.MagicMock(
                        set_tails_file_public_uri=async_mock.CoroutineMock(),
                        generate_registry=async_mock.CoroutineMock(),
                        send_def=async_mock.CoroutineMock(),
                        send_entry=async_mock.CoroutineMock(),
                        stage_pending_registry=async_mock.CoroutineMock(),
                    )
                )
            )
            with self.assertRaises(test_module.web.HTTPInternalServerError):
                await test_module.credential_definitions_send_credential_definition(
                    self.request
                )

    async def test_send_credential_definition_revoc_init_issuer_rev_reg_x(self):
        self.request.json = async_mock.CoroutineMock(
            return_value={
                "schema_id": "WgWxqztrNooG92RXvxSTWv:2:schema_name:1.0",
                "support_revocation": True,
                "tag": "tag",
            }
        )

        self.request.query = {"create_transaction_for_endorser": "false"}

        self.context.profile.settings.set_value(
            "tails_server_base_url", "http://1.2.3.4:8222"
        )

        mock_tails_server = async_mock.MagicMock(
            upload_tails_file=async_mock.CoroutineMock(return_value=(True, None))
        )
        self.profile_injector.bind_instance(BaseTailsServer, mock_tails_server)

        with async_mock.patch.object(
            test_module, "IndyRevocation", async_mock.MagicMock()
        ) as test_indy_revoc:
            test_indy_revoc.return_value = async_mock.MagicMock(
                init_issuer_registry=async_mock.CoroutineMock(
                    side_effect=[
                        async_mock.MagicMock(
                            set_tails_file_public_uri=async_mock.CoroutineMock(),
                            generate_registry=async_mock.CoroutineMock(),
                            send_def=async_mock.CoroutineMock(),
                            send_entry=async_mock.CoroutineMock(),
                        ),
                        test_module.RevocationError("Error on pending rev reg init"),
                    ]
                )
            )
            with self.assertRaises(test_module.web.HTTPBadRequest):
                await test_module.credential_definitions_send_credential_definition(
                    self.request
                )

    async def test_send_credential_definition_create_transaction_for_endorser(self):
        self.request.json = async_mock.CoroutineMock(
            return_value={
                "schema_id": "WgWxqztrNooG92RXvxSTWv:2:schema_name:1.0",
                "support_revocation": False,
                "tag": "tag",
            }
        )

        self.request.query = {
            "create_transaction_for_endorser": "true",
            "conn_id": "dummy",
        }

        with async_mock.patch.object(
            ConnRecord, "retrieve_by_id", async_mock.CoroutineMock()
        ) as mock_conn_rec_retrieve, async_mock.patch.object(
            test_module, "TransactionManager", async_mock.MagicMock()
        ) as mock_txn_mgr, async_mock.patch.object(
            test_module.web, "json_response", async_mock.MagicMock()
        ) as mock_response:
            mock_txn_mgr.return_value = async_mock.MagicMock(
                create_record=async_mock.CoroutineMock(
                    return_value=async_mock.MagicMock(
                        serialize=async_mock.MagicMock(return_value={"...": "..."})
                    )
                )
            )
            mock_conn_rec_retrieve.return_value = async_mock.MagicMock(
                metadata_get=async_mock.CoroutineMock(
                    return_value={
                        "endorser_did": ("did"),
                        "endorser_name": ("name"),
                    }
                )
            )
            result = (
                await test_module.credential_definitions_send_credential_definition(
                    self.request
                )
            )
            assert result == mock_response.return_value
            mock_response.assert_called_once_with({"txn": {"...": "..."}})

    async def test_send_credential_definition_create_transaction_for_endorser_storage_x(
        self,
    ):
        self.request.json = async_mock.CoroutineMock(
            return_value={
                "schema_id": "WgWxqztrNooG92RXvxSTWv:2:schema_name:1.0",
                "support_revocation": False,
                "tag": "tag",
            }
        )

        self.request.query = {
            "create_transaction_for_endorser": "true",
            "conn_id": "dummy",
        }

        with async_mock.patch.object(
            ConnRecord, "retrieve_by_id", async_mock.CoroutineMock()
        ) as mock_conn_rec_retrieve, async_mock.patch.object(
            test_module, "TransactionManager", async_mock.MagicMock()
        ) as mock_txn_mgr:

            mock_conn_rec_retrieve.return_value = async_mock.MagicMock(
                metadata_get=async_mock.CoroutineMock(
                    return_value={
                        "endorser_did": ("did"),
                        "endorser_name": ("name"),
                    }
                )
            )
            mock_txn_mgr.return_value = async_mock.MagicMock(
                create_record=async_mock.CoroutineMock(
                    side_effect=test_module.StorageError()
                )
            )

            with self.assertRaises(test_module.web.HTTPBadRequest):
                await test_module.credential_definitions_send_credential_definition(
                    self.request
                )

    async def test_send_credential_definition_create_transaction_for_endorser_not_found_x(
        self,
    ):
        self.request.json = async_mock.CoroutineMock(
            return_value={
                "schema_id": "WgWxqztrNooG92RXvxSTWv:2:schema_name:1.0",
                "support_revocation": False,
                "tag": "tag",
            }
        )

        self.request.query = {
            "create_transaction_for_endorser": "true",
            "conn_id": "dummy",
        }

        with async_mock.patch.object(
            ConnRecord, "retrieve_by_id", async_mock.CoroutineMock()
        ) as mock_conn_rec_retrieve:
            mock_conn_rec_retrieve.side_effect = test_module.StorageNotFoundError()

            with self.assertRaises(test_module.web.HTTPNotFound):
                await test_module.credential_definitions_send_credential_definition(
                    self.request
                )

    async def test_send_credential_definition_create_transaction_for_endorser_base_model_x(
        self,
    ):
        self.request.json = async_mock.CoroutineMock(
            return_value={
                "schema_id": "WgWxqztrNooG92RXvxSTWv:2:schema_name:1.0",
                "support_revocation": False,
                "tag": "tag",
            }
        )

        self.request.query = {
            "create_transaction_for_endorser": "true",
            "conn_id": "dummy",
        }

        with async_mock.patch.object(
            ConnRecord, "retrieve_by_id", async_mock.CoroutineMock()
        ) as mock_conn_rec_retrieve:
            mock_conn_rec_retrieve.side_effect = test_module.BaseModelError()

            with self.assertRaises(test_module.web.HTTPBadRequest):
                await test_module.credential_definitions_send_credential_definition(
                    self.request
                )

    async def test_send_credential_definition_create_transaction_for_endorser_no_endorser_info_x(
        self,
    ):
        self.request.json = async_mock.CoroutineMock(
            return_value={
                "schema_id": "WgWxqztrNooG92RXvxSTWv:2:schema_name:1.0",
                "support_revocation": False,
                "tag": "tag",
            }
        )

        self.request.query = {
            "create_transaction_for_endorser": "true",
            "conn_id": "dummy",
        }

        with async_mock.patch.object(
            ConnRecord, "retrieve_by_id", async_mock.CoroutineMock()
        ) as mock_conn_rec_retrieve:
            mock_conn_rec_retrieve.return_value = async_mock.MagicMock(
                metadata_get=async_mock.CoroutineMock(return_value=None)
            )
            with self.assertRaises(test_module.web.HTTPForbidden):
                await test_module.credential_definitions_send_credential_definition(
                    self.request
                )

    async def test_send_credential_definition_create_transaction_for_endorser_no_endorser_did_x(
        self,
    ):
        self.request.json = async_mock.CoroutineMock(
            return_value={
                "schema_id": "WgWxqztrNooG92RXvxSTWv:2:schema_name:1.0",
                "support_revocation": False,
                "tag": "tag",
            }
        )

        self.request.query = {
            "create_transaction_for_endorser": "true",
            "conn_id": "dummy",
        }

        with async_mock.patch.object(
            ConnRecord, "retrieve_by_id", async_mock.CoroutineMock()
        ) as mock_conn_rec_retrieve:
            mock_conn_rec_retrieve.return_value = async_mock.MagicMock(
                metadata_get=async_mock.CoroutineMock(
                    return_value={
                        "endorser_name": ("name"),
                    }
                )
            )
            with self.assertRaises(test_module.web.HTTPForbidden):
                await test_module.credential_definitions_send_credential_definition(
                    self.request
                )

    async def test_send_credential_definition_no_ledger(self):
        self.request.json = async_mock.CoroutineMock(
            return_value={
                "schema_id": "WgWxqztrNooG92RXvxSTWv:2:schema_name:1.0",
                "support_revocation": False,
                "tag": "tag",
            }
        )

        self.context.injector.clear_binding(BaseLedger)
        self.profile_injector.clear_binding(BaseLedger)
        with self.assertRaises(test_module.web.HTTPForbidden):
            await test_module.credential_definitions_send_credential_definition(
                self.request
            )

    async def test_send_credential_definition_ledger_x(self):
        self.request.json = async_mock.CoroutineMock(
            return_value={
                "schema_id": "WgWxqztrNooG92RXvxSTWv:2:schema_name:1.0",
                "support_revocation": False,
                "tag": "tag",
            }
        )

        self.request.query = {"create_transaction_for_endorser": "false"}

        self.ledger.__aenter__ = async_mock.CoroutineMock(
            side_effect=test_module.LedgerError("oops")
        )
        with self.assertRaises(test_module.web.HTTPBadRequest):
            await test_module.credential_definitions_send_credential_definition(
                self.request
            )

    async def test_created(self):
        self.request.match_info = {"cred_def_id": CRED_DEF_ID}

        with async_mock.patch.object(test_module.web, "json_response") as mock_response:
            result = await test_module.credential_definitions_created(self.request)
            assert result == mock_response.return_value
            mock_response.assert_called_once_with(
                {"credential_definition_ids": [CRED_DEF_ID]}
            )

    async def test_get_credential_definition(self):
        self.request.match_info = {"cred_def_id": CRED_DEF_ID}

        with async_mock.patch.object(test_module.web, "json_response") as mock_response:
            result = await test_module.credential_definitions_get_credential_definition(
                self.request
            )
            assert result == mock_response.return_value
            mock_response.assert_called_once_with(
                {"credential_definition": {"cred": "def", "signed_txn": "..."}}
            )

    async def test_get_credential_definition_no_ledger(self):
        self.request.match_info = {"cred_def_id": CRED_DEF_ID}

        self.context.injector.clear_binding(BaseLedger)
        self.profile_injector.clear_binding(BaseLedger)
        with self.assertRaises(test_module.web.HTTPForbidden):
            await test_module.credential_definitions_get_credential_definition(
                self.request
            )

    async def test_register(self):
        mock_app = async_mock.MagicMock()
        mock_app.add_routes = async_mock.MagicMock()

        await test_module.register(mock_app)
        mock_app.add_routes.assert_called_once()

    async def test_post_process_routes(self):
        mock_app = async_mock.MagicMock(_state={"swagger_dict": {}})
        test_module.post_process_routes(mock_app)
        assert "tags" in mock_app._state["swagger_dict"]
