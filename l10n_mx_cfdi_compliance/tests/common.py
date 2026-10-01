# -*- coding: utf-8 -*-
# Copyright 2026 ANFEPI - Roberto Requejo Jimenez | License OPL-1
# https://www.anfepi.com — Subscription required, redistribution prohibited.
import base64
import os

from odoo.tests.common import TransactionCase


FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")


def load_fixture(name):
    """Read raw bytes of a fixture XML file."""
    with open(os.path.join(FIXTURES_DIR, name), "rb") as fh:
        return fh.read()


class CfdiComplianceCommon(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Attachment = cls.env["ir.attachment"]
        cls.CfdiDoc = cls.env["l10n_mx.cfdi.document"]
        cls.Profile = cls.env["l10n_mx.compliance.profile"]
        cls.Rule = cls.env["l10n_mx.compliance.rule"]
        cls.AuditLog = cls.env["l10n_mx.compliance.audit.log"]
        cls.env["l10n_mx.compliance.rule"]._sync_from_registry()
        cls.env["res.company"]._l10n_mx_cfdi_create_default_profile()
        cls.company = cls.env.company
        cls.profile = cls.company.default_compliance_profile_id

    def _attach_xml(self, content_bytes, filename="cfdi.xml"):
        return self.Attachment.create({
            "name": filename,
            "datas": base64.b64encode(content_bytes),
            "mimetype": "application/xml",
            "res_model": "l10n_mx.cfdi.document",
            "res_id": 0,
        })
