# -*- coding: utf-8 -*-
{
    'name': "Custom Purchase Process",

    'summary': "Purchase Request and Store Requisition Management for Odoo Community",

    'description': """
        Custom Purchase Process Module
        ==============================
        This module manages purchase requests, store requisitions, supplier analysis,
        and quality inspections with approval workflows.
        
        Features:
        - Store Requisition (Material Request) management
        - Purchase Request workflow
        - RFQ (Request for Quotation) generation
        - Supplier Analysis and evaluation
        - Quality Inspection management
        - Store Issue Voucher (SIV) generation
        - Bell notifications (next in line, earlier handlers and pop-ups) through
          generic_bell_notification
    """,

    'author': "Your Company",
    'website': "http://www.yourcompany.com",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/18.0/odoo/addons/base/data/ir_module_category_data.xml
    # for the full list
    'category': 'Purchases',
    'version': '18.0.1.9.2',

    # any module necessary for this one to work correctly
    'depends': ['base', 'account', 'mail', 'stock', 'purchase', 'hr', 'analytic', 'project', 'mefs_bill_of_quantity', 'generic_bell_notification'],

    # always loaded
    'data': [
        # 'data/user_groups.xml',
        'data/purchase_quotation_reports.xml',
        'data/ir_sequence_data.xml',
        'data/purchase_quotation_sequence.xml',
        


        
        'security/material_request_security.xml',
        'security/purchase_request_security.xml',
        'security/supplier_analysis_security.xml',
        'security/store_request_security.xml',
        'security/material_request_rules.xml',
        'security/purchase_request_record_rules.xml',
        'security/store_rquest_record_rules.xml',
        'security/supplier_analysis_record_rules.xml',
        'security/quality_inspection_security_group.xml',
        'security/quality_inspection_record_rules.xml',
        'security/res_user_access_control_rules.xml',
        'security/ir.model.access.csv',

        'views/create_siv_views.xml',
        'views/custom_purchase_order_views.xml',
        'data/purchase_order_list_columns.xml',
        'views/inherited_stock_location_views.xml',
        'views/material_request_view.xml',
        'views/purchase_request_views.xml',
        'views/purchase_quotation_views.xml',
        'wizards/back_to_sr_wizard_views.xml',
        'wizards/reject_purchase_request_wizard_views.xml',
        # 'views/sales_request_form_views.xml',
        'views/supplier_analysis_views.xml',
        'views/res_user_access_control_views.xml',
        'views/supplier_analysis_thereshold_view.xml',
        'views/quality_inspection_views.xml',

        'report/report_purchase_quotation.xml',
        'report/material_request_report.xml',
        'report/purchase_request_report.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'custom_purchase_process/static/src/xml/template.xml',
            'custom_purchase_process/static/src/scss/style.scss',
        ],
        'web.report_assets_common':['custom_purchase_process/static/src/css/my_fonts.css'],
    },
    # only loaded in demonstration mode
    'demo': [
        'demo/demo.xml',        
    ],
}
