#   Copyright 2013 OpenStack Foundation
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

"""Keypair action implementations"""

import io
import logging
import os
import sys

from novaclient import api_versions
from osc_lib.command import command
from osc_lib import exceptions
from osc_lib import utils

from openstackclient.i18n import _
from openstackclient.identity import common as identity_common


LOG = logging.getLogger(__name__)


class CreateKeypair(command.ShowOne):
    _description = _("Create new public or private key for server ssh access")

    def get_parser(self, prog_name):
        parser = super(CreateKeypair, self).get_parser(prog_name)
        parser.add_argument(
            'name',
            metavar='<name>',
            help=_("New public or private key name")
        )
        key_group = parser.add_mutually_exclusive_group()
        key_group.add_argument(
            '--public-key',
            metavar='<file>',
            help=_("Filename for public key to add. If not used, "
                   "creates a private key.")
        )
        key_group.add_argument(
            '--private-key',
            metavar='<file>',
            help=_("Filename for private key to save. If not used, "
                   "print private key in console.")
        )
        parser.add_argument(
            '--type',
            metavar='<type>',
            choices=['ssh', 'x509'],
            help=_(
                "Keypair type. Can be ssh or x509. "
                "(Supported by API versions '2.2' - '2.latest')"
            ),
        )
        parser.add_argument(
            '--user',
            metavar='<user>',
            help=_(
                'The owner of the keypair. (admin only) (name or ID). '
                'Requires ``--os-compute-api-version`` 2.10 or greater.'
            ),
        )
        identity_common.add_user_domain_option_to_parser(parser)
        return parser

    def take_action(self, parsed_args):
        compute_client = self.app.client_manager.compute
        identity_client = self.app.client_manager.identity

        public_key = parsed_args.public_key
        if public_key:
            try:
                with io.open(os.path.expanduser(parsed_args.public_key)) as p:
                    public_key = p.read()
            except IOError as e:
                msg = _("Key file %(public_key)s not found: %(exception)s")
                raise exceptions.CommandError(
                    msg % {"public_key": parsed_args.public_key,
                           "exception": e}
                )

        kwargs = {
            'name': parsed_args.name,
            'public_key': public_key,
        }
        if parsed_args.type:
            if compute_client.api_version < api_versions.APIVersion('2.2'):
                msg = _(
                    '--os-compute-api-version 2.2 or greater is required to '
                    'support the --type option'
                )
                raise exceptions.CommandError(msg)

            kwargs['key_type'] = parsed_args.type

        if parsed_args.user:
            if compute_client.api_version < api_versions.APIVersion('2.10'):
                msg = _(
                    '--os-compute-api-version 2.10 or greater is required to '
                    'support the --user option'
                )
                raise exceptions.CommandError(msg)

            kwargs['user_id'] = identity_common.find_user(
                identity_client,
                parsed_args.user,
                parsed_args.user_domain,
            ).id

        keypair = compute_client.keypairs.create(**kwargs)

        private_key = parsed_args.private_key
        # Save private key into specified file
        if private_key:
            try:
                with io.open(
                    os.path.expanduser(parsed_args.private_key), 'w+'
                ) as p:
                    p.write(keypair.private_key)
            except IOError as e:
                msg = _("Key file %(private_key)s can not be saved: "
                        "%(exception)s")
                raise exceptions.CommandError(
                    msg % {"private_key": parsed_args.private_key,
                           "exception": e}
                )
        # NOTE(dtroyer): how do we want to handle the display of the private
        #                key when it needs to be communicated back to the user
        #                For now, duplicate nova keypair-add command output
        info = {}
        if public_key or private_key:
            info.update(keypair._info)
            if 'public_key' in info:
                del info['public_key']
            if 'private_key' in info:
                del info['private_key']
            return zip(*sorted(info.items()))
        else:
            sys.stdout.write(keypair.private_key)
            return ({}, {})


class DeleteKeypair(command.Command):
    _description = _("Delete public or private key(s)")

    def get_parser(self, prog_name):
        parser = super(DeleteKeypair, self).get_parser(prog_name)
        parser.add_argument(
            'name',
            metavar='<key>',
            nargs='+',
            help=_("Name of key(s) to delete (name only)")
        )
        parser.add_argument(
            '--user',
            metavar='<user>',
            help=_(
                'The owner of the keypair. (admin only) (name or ID). '
                'Requires ``--os-compute-api-version`` 2.10 or greater.'
            ),
        )
        identity_common.add_user_domain_option_to_parser(parser)
        return parser

    def take_action(self, parsed_args):
        compute_client = self.app.client_manager.compute
        identity_client = self.app.client_manager.identity

        kwargs = {}
        result = 0

        if parsed_args.user:
            if compute_client.api_version < api_versions.APIVersion('2.10'):
                msg = _(
                    '--os-compute-api-version 2.10 or greater is required to '
                    'support the --user option'
                )
                raise exceptions.CommandError(msg)

            kwargs['user_id'] = identity_common.find_user(
                identity_client,
                parsed_args.user,
                parsed_args.user_domain,
            ).id

        for n in parsed_args.name:
            try:
                data = utils.find_resource(
                    compute_client.keypairs, n)
                compute_client.keypairs.delete(data.name, **kwargs)
            except Exception as e:
                result += 1
                LOG.error(_("Failed to delete key with name "
                          "'%(name)s': %(e)s"), {'name': n, 'e': e})

        if result > 0:
            total = len(parsed_args.name)
            msg = (_("%(result)s of %(total)s keys failed "
                   "to delete.") % {'result': result, 'total': total})
            raise exceptions.CommandError(msg)


class ListKeypair(command.Lister):
    _description = _("List key fingerprints")

    def get_parser(self, prog_name):
        parser = super().get_parser(prog_name)
        user_group = parser.add_mutually_exclusive_group()
        user_group.add_argument(
            '--user',
            metavar='<user>',
            help=_(
                'Show keypairs for another user (admin only) (name or ID). '
                'Requires ``--os-compute-api-version`` 2.10 or greater.'
            ),
        )
        identity_common.add_user_domain_option_to_parser(parser)
        user_group.add_argument(
            '--project',
            metavar='<project>',
            help=_(
                'Show keypairs for all users associated with project '
                '(admin only) (name or ID). '
                'Requires ``--os-compute-api-version`` 2.10 or greater.'
            ),
        )
        identity_common.add_project_domain_option_to_parser(parser)
        return parser

    def take_action(self, parsed_args):
        compute_client = self.app.client_manager.compute
        identity_client = self.app.client_manager.identity

        if parsed_args.project:
            if compute_client.api_version < api_versions.APIVersion('2.10'):
                msg = _(
                    '--os-compute-api-version 2.10 or greater is required to '
                    'support the --project option'
                )
                raise exceptions.CommandError(msg)

            # NOTE(stephenfin): This is done client side because nova doesn't
            # currently support doing so server-side. If this is slow, we can
            # think about spinning up a threadpool or similar.
            project = identity_common.find_project(
                identity_client,
                parsed_args.project,
                parsed_args.project_domain,
            ).id
            users = identity_client.users.list(tenant_id=project)

            data = []
            for user in users:
                data.extend(compute_client.keypairs.list(user_id=user.id))
        elif parsed_args.user:
            if compute_client.api_version < api_versions.APIVersion('2.10'):
                msg = _(
                    '--os-compute-api-version 2.10 or greater is required to '
                    'support the --user option'
                )
                raise exceptions.CommandError(msg)

            user = identity_common.find_user(
                identity_client,
                parsed_args.user,
                parsed_args.user_domain,
            )

            data = compute_client.keypairs.list(user_id=user.id)
        else:
            data = compute_client.keypairs.list()

        columns = (
            "Name",
            "Fingerprint"
        )

        if compute_client.api_version >= api_versions.APIVersion('2.2'):
            columns += ("Type", )

        return (
            columns,
            (utils.get_item_properties(s, columns) for s in data),
        )


class ShowKeypair(command.ShowOne):
    _description = _("Display key details")

    def get_parser(self, prog_name):
        parser = super(ShowKeypair, self).get_parser(prog_name)
        parser.add_argument(
            'name',
            metavar='<key>',
            help=_("Public or private key to display (name only)")
        )
        parser.add_argument(
            '--public-key',
            action='store_true',
            default=False,
            help=_("Show only bare public key paired with the generated key")
        )
        parser.add_argument(
            '--user',
            metavar='<user>',
            help=_(
                'The owner of the keypair. (admin only) (name or ID). '
                'Requires ``--os-compute-api-version`` 2.10 or greater.'
            ),
        )
        identity_common.add_user_domain_option_to_parser(parser)
        return parser

    def take_action(self, parsed_args):
        compute_client = self.app.client_manager.compute
        identity_client = self.app.client_manager.identity

        kwargs = {}

        if parsed_args.user:
            if compute_client.api_version < api_versions.APIVersion('2.10'):
                msg = _(
                    '--os-compute-api-version 2.10 or greater is required to '
                    'support the --user option'
                )
                raise exceptions.CommandError(msg)

            kwargs['user_id'] = identity_common.find_user(
                identity_client,
                parsed_args.user,
                parsed_args.user_domain,
            ).id

        keypair = utils.find_resource(
            compute_client.keypairs, parsed_args.name, **kwargs)

        info = {}
        info.update(keypair._info)
        if not parsed_args.public_key:
            del info['public_key']
            return zip(*sorted(info.items()))
        else:
            # NOTE(dtroyer): a way to get the public key in a similar form
            #                as the private key in the create command
            sys.stdout.write(keypair.public_key)
            return ({}, {})
