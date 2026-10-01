# Copyright 2022 Vauxoo
# License LGPL-3 or later (http://www.gnu.org/licenses/lgpl).
{
    "name": "Split Payment",
    "summary": """
    Module that allows to create payments for several invoices at once, fully
    or partially, and while doing so the Journal Entries are created with one
    line per invoice being paid. If invoices for different partners are
    selected, It will create on payment for each partner. Other conditions for
    groupings apply.
    """,
    "author": "Vauxoo & German Ponce",
    "website": "https://poncesoft.blogspot.com",
    "license": "LGPL-3",
    "category": "Installer",
    "version": "1.8",
    "depends": [
        "account",
    ],
    "data": [
        "security/ir.model.access.csv",
        "views/account_payment.xml",
        "views/account_move_views.xml",
    ],
    "demo": [],
    "installable": True,
    "auto_install": False,
}
