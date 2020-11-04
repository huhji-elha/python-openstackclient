#   Copyright 2016 IBM
#
#   Licensed under the Apache License, Version 2.0 (the "License"); you may
#   not use this file except in compliance with the License. You may obtain
#   a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#   WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#   License for the specific language governing permissions and limitations
#   under the License.
#

import copy
from unittest import mock
from unittest.mock import call
import uuid

from novaclient import api_versions
from osc_lib import exceptions
from osc_lib import utils

from openstackclient.compute.v2 import keypair
from openstackclient.tests.unit.compute.v2 import fakes as compute_fakes
from openstackclient.tests.unit import fakes
from openstackclient.tests.unit.identity.v2_0 import fakes as identity_fakes
from openstackclient.tests.unit import utils as tests_utils


class TestKeypair(compute_fakes.TestComputev2):

    def setUp(self):
        super(TestKeypair, self).setUp()

        # Get a shortcut to the KeypairManager Mock
        self.keypairs_mock = self.app.client_manager.compute.keypairs
        self.keypairs_mock.reset_mock()

        # Initialize the user mock
        self.users_mock = self.app.client_manager.identity.users
        self.users_mock.reset_mock()
        self.users_mock.get.return_value = fakes.FakeResource(
            None,
            copy.deepcopy(identity_fakes.USER),
            loaded=True,
        )


class TestKeypairCreate(TestKeypair):

    keypair = compute_fakes.FakeKeypair.create_one_keypair()

    def setUp(self):
        super(TestKeypairCreate, self).setUp()

        self.columns = (
            'fingerprint',
            'name',
            'type',
            'user_id'
        )
        self.data = (
            self.keypair.fingerprint,
            self.keypair.name,
            self.keypair.type,
            self.keypair.user_id
        )

        # Get the command object to test
        self.cmd = keypair.CreateKeypair(self.app, None)

        self.keypairs_mock.create.return_value = self.keypair

    def test_key_pair_create_no_options(self):

        arglist = [
            self.keypair.name,
        ]
        verifylist = [
            ('name', self.keypair.name),
        ]
        parsed_args = self.check_parser(self.cmd, arglist, verifylist)

        columns, data = self.cmd.take_action(parsed_args)

        self.keypairs_mock.create.assert_called_with(
            name=self.keypair.name,
            public_key=None
        )

        self.assertEqual({}, columns)
        self.assertEqual({}, data)

    def test_keypair_create_public_key(self):
        # overwrite the setup one because we want to omit private_key
        self.keypair = compute_fakes.FakeKeypair.create_one_keypair(
            no_pri=True)
        self.keypairs_mock.create.return_value = self.keypair

        self.data = (
            self.keypair.fingerprint,
            self.keypair.name,
            self.keypair.type,
            self.keypair.user_id
        )

        arglist = [
            '--public-key', self.keypair.public_key,
            self.keypair.name,
        ]
        verifylist = [
            ('public_key', self.keypair.public_key),
            ('name', self.keypair.name),
        ]

        parsed_args = self.check_parser(self.cmd, arglist, verifylist)

        with mock.patch('io.open') as mock_open:
            mock_open.return_value = mock.MagicMock()
            m_file = mock_open.return_value.__enter__.return_value
            m_file.read.return_value = 'dummy'

            columns, data = self.cmd.take_action(parsed_args)

            self.keypairs_mock.create.assert_called_with(
                name=self.keypair.name,
                public_key=self.keypair.public_key,
            )

            self.assertEqual(self.columns, columns)
            self.assertEqual(self.data, data)

    def test_keypair_create_private_key(self):
        tmp_pk_file = '/tmp/kp-file-' + uuid.uuid4().hex
        arglist = [
            '--private-key', tmp_pk_file,
            self.keypair.name,
        ]
        verifylist = [
            ('private_key', tmp_pk_file),
            ('name', self.keypair.name),
        ]

        parsed_args = self.check_parser(self.cmd, arglist, verifylist)

        with mock.patch('io.open') as mock_open:
            mock_open.return_value = mock.MagicMock()
            m_file = mock_open.return_value.__enter__.return_value

            columns, data = self.cmd.take_action(parsed_args)

            self.keypairs_mock.create.assert_called_with(
                name=self.keypair.name,
                public_key=None,
            )

            mock_open.assert_called_once_with(tmp_pk_file, 'w+')
            m_file.write.assert_called_once_with(self.keypair.private_key)

            self.assertEqual(self.columns, columns)
            self.assertEqual(self.data, data)

    def test_keypair_create_with_key_type(self):
        self.app.client_manager.compute.api_version = api_versions.APIVersion(
            '2.2')

        for key_type in ['x509', 'ssh']:
            self.keypair = compute_fakes.FakeKeypair.create_one_keypair(
                no_pri=True)
            self.keypairs_mock.create.return_value = self.keypair

            self.data = (
                self.keypair.fingerprint,
                self.keypair.name,
                self.keypair.type,
                self.keypair.user_id,
            )
            arglist = [
                '--public-key', self.keypair.public_key,
                self.keypair.name,
                '--type', key_type,
            ]
            verifylist = [
                ('public_key', self.keypair.public_key),
                ('name', self.keypair.name),
                ('type', key_type),
            ]
            parsed_args = self.check_parser(self.cmd, arglist, verifylist)

            with mock.patch('io.open') as mock_open:
                mock_open.return_value = mock.MagicMock()
                m_file = mock_open.return_value.__enter__.return_value
                m_file.read.return_value = 'dummy'
                columns, data = self.cmd.take_action(parsed_args)

            self.keypairs_mock.create.assert_called_with(
                name=self.keypair.name,
                public_key=self.keypair.public_key,
                key_type=key_type,
            )

            self.assertEqual(self.columns, columns)
            self.assertEqual(self.data, data)

    def test_keypair_create_with_key_type_pre_v22(self):
        self.app.client_manager.compute.api_version = api_versions.APIVersion(
            '2.1')

        for key_type in ['x509', 'ssh']:
            arglist = [
                '--public-key', self.keypair.public_key,
                self.keypair.name,
                '--type', 'ssh',
            ]
            verifylist = [
                ('public_key', self.keypair.public_key),
                ('name', self.keypair.name),
                ('type', 'ssh'),
            ]
            parsed_args = self.check_parser(self.cmd, arglist, verifylist)

            with mock.patch('io.open') as mock_open:
                mock_open.return_value = mock.MagicMock()
                m_file = mock_open.return_value.__enter__.return_value
                m_file.read.return_value = 'dummy'

                ex = self.assertRaises(
                    exceptions.CommandError,
                    self.cmd.take_action,
                    parsed_args)

            self.assertIn(
                '--os-compute-api-version 2.2 or greater is required',
                str(ex))

    def test_key_pair_create_with_user(self):

        self.app.client_manager.compute.api_version = \
            api_versions.APIVersion('2.10')

        arglist = [
            '--user', identity_fakes.user_name,
            self.keypair.name,
        ]
        verifylist = [
            ('user', identity_fakes.user_name),
            ('name', self.keypair.name),
        ]
        parsed_args = self.check_parser(self.cmd, arglist, verifylist)

        columns, data = self.cmd.take_action(parsed_args)

        self.keypairs_mock.create.assert_called_with(
            name=self.keypair.name,
            public_key=None,
            user_id=identity_fakes.user_id,
        )

        self.assertEqual({}, columns)
        self.assertEqual({}, data)

    def test_key_pair_create_with_user_pre_v210(self):

        self.app.client_manager.compute.api_version = \
            api_versions.APIVersion('2.9')

        arglist = [
            '--user', identity_fakes.user_name,
            self.keypair.name,
        ]
        verifylist = [
            ('user', identity_fakes.user_name),
            ('name', self.keypair.name),
        ]
        parsed_args = self.check_parser(self.cmd, arglist, verifylist)

        ex = self.assertRaises(
            exceptions.CommandError,
            self.cmd.take_action,
            parsed_args)
        self.assertIn(
            '--os-compute-api-version 2.10 or greater is required', str(ex))


class TestKeypairDelete(TestKeypair):

    keypairs = compute_fakes.FakeKeypair.create_keypairs(count=2)

    def setUp(self):
        super(TestKeypairDelete, self).setUp()

        self.keypairs_mock.get = compute_fakes.FakeKeypair.get_keypairs(
            self.keypairs)
        self.keypairs_mock.delete.return_value = None

        self.cmd = keypair.DeleteKeypair(self.app, None)

    def test_keypair_delete(self):
        arglist = [
            self.keypairs[0].name
        ]
        verifylist = [
            ('name', [self.keypairs[0].name]),
        ]

        parsed_args = self.check_parser(self.cmd, arglist, verifylist)

        ret = self.cmd.take_action(parsed_args)

        self.assertIsNone(ret)
        self.keypairs_mock.delete.assert_called_with(self.keypairs[0].name)

    def test_delete_multiple_keypairs(self):
        arglist = []
        for k in self.keypairs:
            arglist.append(k.name)
        verifylist = [
            ('name', arglist),
        ]

        parsed_args = self.check_parser(self.cmd, arglist, verifylist)
        result = self.cmd.take_action(parsed_args)

        calls = []
        for k in self.keypairs:
            calls.append(call(k.name))
        self.keypairs_mock.delete.assert_has_calls(calls)
        self.assertIsNone(result)

    def test_delete_multiple_keypairs_with_exception(self):
        arglist = [
            self.keypairs[0].name,
            'unexist_keypair',
        ]
        verifylist = [
            ('name', arglist),
        ]

        parsed_args = self.check_parser(self.cmd, arglist, verifylist)

        find_mock_result = [self.keypairs[0], exceptions.CommandError]
        with mock.patch.object(utils, 'find_resource',
                               side_effect=find_mock_result) as find_mock:
            try:
                self.cmd.take_action(parsed_args)
                self.fail('CommandError should be raised.')
            except exceptions.CommandError as e:
                self.assertEqual('1 of 2 keys failed to delete.', str(e))

            find_mock.assert_any_call(
                self.keypairs_mock, self.keypairs[0].name)
            find_mock.assert_any_call(self.keypairs_mock, 'unexist_keypair')

            self.assertEqual(2, find_mock.call_count)
            self.keypairs_mock.delete.assert_called_once_with(
                self.keypairs[0].name
            )

    def test_keypair_delete_with_user(self):

        self.app.client_manager.compute.api_version = \
            api_versions.APIVersion('2.10')

        arglist = [
            '--user', identity_fakes.user_name,
            self.keypairs[0].name
        ]
        verifylist = [
            ('user', identity_fakes.user_name),
            ('name', [self.keypairs[0].name]),
        ]
        parsed_args = self.check_parser(self.cmd, arglist, verifylist)

        ret = self.cmd.take_action(parsed_args)

        self.assertIsNone(ret)
        self.keypairs_mock.delete.assert_called_with(
            self.keypairs[0].name,
            user_id=identity_fakes.user_id,
        )

    def test_keypair_delete_with_user_pre_v210(self):

        self.app.client_manager.compute.api_version = \
            api_versions.APIVersion('2.9')

        arglist = [
            '--user', identity_fakes.user_name,
            self.keypairs[0].name
        ]
        verifylist = [
            ('user', identity_fakes.user_name),
            ('name', [self.keypairs[0].name]),
        ]
        parsed_args = self.check_parser(self.cmd, arglist, verifylist)

        ex = self.assertRaises(
            exceptions.CommandError,
            self.cmd.take_action,
            parsed_args)
        self.assertIn(
            '--os-compute-api-version 2.10 or greater is required', str(ex))


class TestKeypairList(TestKeypair):

    # Return value of self.keypairs_mock.list().
    keypairs = compute_fakes.FakeKeypair.create_keypairs(count=1)

    def setUp(self):
        super(TestKeypairList, self).setUp()

        self.keypairs_mock.list.return_value = self.keypairs

        # Get the command object to test
        self.cmd = keypair.ListKeypair(self.app, None)

    def test_keypair_list_no_options(self):
        arglist = []
        verifylist = []

        parsed_args = self.check_parser(self.cmd, arglist, verifylist)

        # In base command class Lister in cliff, abstract method take_action()
        # returns a tuple containing the column names and an iterable
        # containing the data to be listed.
        columns, data = self.cmd.take_action(parsed_args)

        # Set expected values

        self.keypairs_mock.list.assert_called_with()

        self.assertEqual(('Name', 'Fingerprint'), columns)
        self.assertEqual(
            ((self.keypairs[0].name, self.keypairs[0].fingerprint), ),
            tuple(data)
        )

    def test_keypair_list_v22(self):
        self.app.client_manager.compute.api_version = \
            api_versions.APIVersion('2.2')

        arglist = []
        verifylist = []

        parsed_args = self.check_parser(self.cmd, arglist, verifylist)

        # In base command class Lister in cliff, abstract method take_action()
        # returns a tuple containing the column names and an iterable
        # containing the data to be listed.
        columns, data = self.cmd.take_action(parsed_args)

        # Set expected values

        self.keypairs_mock.list.assert_called_with()

        self.assertEqual(('Name', 'Fingerprint', 'Type'), columns)
        self.assertEqual(
            ((
                self.keypairs[0].name,
                self.keypairs[0].fingerprint,
                self.keypairs[0].type,
            ), ),
            tuple(data)
        )

    def test_keypair_list_with_user(self):

        # Filtering by user is support for nova api 2.10 or above
        self.app.client_manager.compute.api_version = \
            api_versions.APIVersion('2.10')

        users_mock = self.app.client_manager.identity.users
        users_mock.reset_mock()
        users_mock.get.return_value = fakes.FakeResource(
            None,
            copy.deepcopy(identity_fakes.USER),
            loaded=True,
        )

        arglist = [
            '--user', identity_fakes.user_name,
        ]
        verifylist = [
            ('user', identity_fakes.user_name),
        ]
        parsed_args = self.check_parser(self.cmd, arglist, verifylist)

        columns, data = self.cmd.take_action(parsed_args)

        users_mock.get.assert_called_with(identity_fakes.user_name)
        self.keypairs_mock.list.assert_called_with(
            user_id=identity_fakes.user_id,
        )

        self.assertEqual(('Name', 'Fingerprint', 'Type'), columns)
        self.assertEqual(
            ((
                self.keypairs[0].name,
                self.keypairs[0].fingerprint,
                self.keypairs[0].type,
            ), ),
            tuple(data)
        )

    def test_keypair_list_with_user_pre_v210(self):

        self.app.client_manager.compute.api_version = \
            api_versions.APIVersion('2.9')

        arglist = [
            '--user', identity_fakes.user_name,
        ]
        verifylist = [
            ('user', identity_fakes.user_name),
        ]
        parsed_args = self.check_parser(self.cmd, arglist, verifylist)

        ex = self.assertRaises(
            exceptions.CommandError,
            self.cmd.take_action,
            parsed_args)
        self.assertIn(
            '--os-compute-api-version 2.10 or greater is required', str(ex))

    def test_keypair_list_with_project(self):

        # Filtering by user is support for nova api 2.10 or above
        self.app.client_manager.compute.api_version = \
            api_versions.APIVersion('2.10')

        projects_mock = self.app.client_manager.identity.tenants
        projects_mock.reset_mock()
        projects_mock.get.return_value = fakes.FakeResource(
            None,
            copy.deepcopy(identity_fakes.PROJECT),
            loaded=True,
        )

        users_mock = self.app.client_manager.identity.users
        users_mock.reset_mock()
        users_mock.list.return_value = [
            fakes.FakeResource(
                None,
                copy.deepcopy(identity_fakes.USER),
                loaded=True,
            ),
        ]

        arglist = ['--project', identity_fakes.project_name]
        verifylist = [('project', identity_fakes.project_name)]
        parsed_args = self.check_parser(self.cmd, arglist, verifylist)

        columns, data = self.cmd.take_action(parsed_args)

        projects_mock.get.assert_called_with(identity_fakes.project_name)
        users_mock.list.assert_called_with(tenant_id=identity_fakes.project_id)
        self.keypairs_mock.list.assert_called_with(
            user_id=identity_fakes.user_id,
        )

        self.assertEqual(('Name', 'Fingerprint', 'Type'), columns)
        self.assertEqual(
            ((
                self.keypairs[0].name,
                self.keypairs[0].fingerprint,
                self.keypairs[0].type,
            ), ),
            tuple(data)
        )

    def test_keypair_list_with_project_pre_v210(self):

        self.app.client_manager.compute.api_version = \
            api_versions.APIVersion('2.9')

        arglist = ['--project', identity_fakes.project_name]
        verifylist = [('project', identity_fakes.project_name)]

        parsed_args = self.check_parser(self.cmd, arglist, verifylist)
        ex = self.assertRaises(
            exceptions.CommandError,
            self.cmd.take_action,
            parsed_args)
        self.assertIn(
            '--os-compute-api-version 2.10 or greater is required', str(ex))

    def test_keypair_list_conflicting_user_options(self):

        # Filtering by user is support for nova api 2.10 or above
        self.app.client_manager.compute.api_version = \
            api_versions.APIVersion('2.10')

        arglist = [
            '--user', identity_fakes.user_name,
            '--project', identity_fakes.project_name,
        ]

        self.assertRaises(
            tests_utils.ParserException,
            self.check_parser, self.cmd, arglist, None)


class TestKeypairShow(TestKeypair):

    keypair = compute_fakes.FakeKeypair.create_one_keypair()

    def setUp(self):
        super(TestKeypairShow, self).setUp()

        self.keypairs_mock.get.return_value = self.keypair

        self.cmd = keypair.ShowKeypair(self.app, None)

        self.columns = (
            "fingerprint",
            "name",
            "type",
            "user_id"
        )

        self.data = (
            self.keypair.fingerprint,
            self.keypair.name,
            self.keypair.type,
            self.keypair.user_id
        )

    def test_keypair_show_no_options(self):

        arglist = []
        verifylist = []

        # Missing required args should boil here
        self.assertRaises(tests_utils.ParserException, self.check_parser,
                          self.cmd, arglist, verifylist)

    def test_keypair_show(self):
        # overwrite the setup one because we want to omit private_key
        self.keypair = compute_fakes.FakeKeypair.create_one_keypair(
            no_pri=True)
        self.keypairs_mock.get.return_value = self.keypair

        self.data = (
            self.keypair.fingerprint,
            self.keypair.name,
            self.keypair.type,
            self.keypair.user_id
        )

        arglist = [
            self.keypair.name
        ]
        verifylist = [
            ('name', self.keypair.name)
        ]
        parsed_args = self.check_parser(self.cmd, arglist, verifylist)

        columns, data = self.cmd.take_action(parsed_args)

        self.keypairs_mock.get.assert_called_with(
            self.keypair.name,
        )

        self.assertEqual(self.columns, columns)
        self.assertEqual(self.data, data)

    def test_keypair_show_public(self):

        arglist = [
            '--public-key',
            self.keypair.name
        ]
        verifylist = [
            ('public_key', True),
            ('name', self.keypair.name)
        ]

        parsed_args = self.check_parser(self.cmd, arglist, verifylist)

        columns, data = self.cmd.take_action(parsed_args)

        self.assertEqual({}, columns)
        self.assertEqual({}, data)

    def test_keypair_show_with_user(self):

        # overwrite the setup one because we want to omit private_key
        self.keypair = compute_fakes.FakeKeypair.create_one_keypair(
            no_pri=True)
        self.keypairs_mock.get.return_value = self.keypair

        self.data = (
            self.keypair.fingerprint,
            self.keypair.name,
            self.keypair.type,
            self.keypair.user_id
        )

        self.app.client_manager.compute.api_version = \
            api_versions.APIVersion('2.10')

        arglist = [
            '--user', identity_fakes.user_name,
            self.keypair.name,
        ]
        verifylist = [
            ('user', identity_fakes.user_name),
            ('name', self.keypair.name)
        ]
        parsed_args = self.check_parser(self.cmd, arglist, verifylist)

        columns, data = self.cmd.take_action(parsed_args)

        self.users_mock.get.assert_called_with(identity_fakes.user_name)
        self.keypairs_mock.get.assert_called_with(
            self.keypair.name,
        )

        self.assertEqual(self.columns, columns)
        self.assertEqual(self.data, data)

    def test_keypair_show_with_user_pre_v210(self):

        arglist = [
            '--user', identity_fakes.user_name,
            self.keypair.name,
        ]
        verifylist = [
            ('user', identity_fakes.user_name),
            ('name', self.keypair.name)
        ]
        parsed_args = self.check_parser(self.cmd, arglist, verifylist)

        ex = self.assertRaises(
            exceptions.CommandError,
            self.cmd.take_action,
            parsed_args)
        self.assertIn(
            '--os-compute-api-version 2.10 or greater is required', str(ex))
