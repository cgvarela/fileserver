# -*- coding: utf-8 -*-
"""Authentication utilities."""
"""
  Kontalk Fileserver
  Copyright (C) 2015 Kontalk Devteam <devteam@kontalk.org>

 This program is free software: you can redistribute it and/or modify
 it under the terms of the GNU General Public License as published by
 the Free Software Foundation, either version 3 of the License, or
 (at your option) any later version.

 This program is distributed in the hope that it will be useful,
 but WITHOUT ANY WARRANTY; without even the implied warranty of
 MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 GNU General Public License for more details.

 You should have received a copy of the GNU General Public License
 along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""


from zope.interface import implements

from twisted.web import iweb
from twisted.cred import credentials, checkers, error, portal
from twisted.python import failure
from twisted.internet import defer
from twisted.words.protocols.jabber import jid, sasl

from gnutls.crypto import OpenPGPCertificate
from OpenSSL.crypto import X509

import log
import keyring


class IKontalkCertificate(credentials.ICredentials):

    def check(fingerprint, kr, verify_cb=None):
        pass


class KontalkCertificate(object):
    implements(IKontalkCertificate)

    def __init__(self, cert):
        self.cert = cert

    def check(self, fingerprint, kr, verify_cb=None):
        _jid = None
        fpr = None

        if isinstance(self.cert, OpenPGPCertificate):
            uid = self.cert.uid(0)
            _jid = jid.JID(uid.email)
            fpr = self.cert.fingerprint

        elif isinstance(self.cert, X509):
            fpr = keyring.verify_certificate(self.cert, kr)
            if fpr:
                pkey = kr.get_key(fpr)
                uid = pkey.uids[0]
                if uid:
                    _jid = jid.JID(uid.email)
                    fpr = kr.check_user_key(pkey, _jid.user)
                    if not fpr:
                        _jid = None

        if _jid:
            def _continue(userjid):
                return userjid
            def _error(reason):
                return None

            # deferred to check fingerprint against JID cache data
            if verify_cb:
                d = verify_cb(_jid, fpr)
                d.addCallback(_continue)
                d.addErrback(_error)
                return d
            else:
                return _jid

        return None


class IKontalkToken(credentials.ICredentials):

    def check(fingerprint, kr, verify_cb):
        pass


class KontalkToken(object):
    implements(IKontalkToken)

    def __init__(self, token, decode_b64=False):
        self.token = token
        self.decode_b64 = decode_b64

    def check(self, fingerprint, kr, verify_cb):
        try:
            if self.decode_b64:
                data = sasl.fromBase64(self.token)
            else:
                data = self.token

            return kr.check_token(data)
        except:
            # TODO logging or throw exception back
            import traceback
            traceback.print_exc()
            log.debug("token verification failed!")


class AuthKontalkChecker(object):
    implements(checkers.ICredentialsChecker)

    credentialInterfaces = IKontalkToken, IKontalkCertificate

    def __init__(self, fingerprint, kr, verify_cb=None):
        self.fingerprint = str(fingerprint)
        self.keyring = kr
        self.verify_cb = verify_cb

    def _cbTokenValid(self, userid):
        if userid:
            return userid
        else:
            return failure.Failure(error.UnauthorizedLogin())

    def requestAvatarId(self, credentials):
        return defer.maybeDeferred(
            credentials.check, self.fingerprint, self.keyring, self.verify_cb).addCallback(
            self._cbTokenValid)


class AuthKontalkTokenFactory(object):
    implements(iweb.ICredentialFactory)

    scheme = 'kontalktoken'

    def __init__(self, fingerprint, kr):
        self.fingerprint = fingerprint
        self.keyring = kr

    def getChallenge(self, request):
        return {}

    def decode(self, response, request):
        key, token = response.split('=', 1)
        if key == 'auth':
            return KontalkToken(token, True)

        raise error.LoginFailed('Invalid token')
