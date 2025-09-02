from odoo import models, fields


class VehicleDocument(models.Model):
    _name = "vehicle.document"
    _description = "Vehicle Documents"
    _rec_name = "document_name"  # 1
    _order = "upload_date desc"  # 1

    vehicle_id = fields.Many2one(
        "vehicle.registration", string="Vehicle", required=True, ondelete="cascade"
    )
    document_name = fields.Char(string="Document Name", required=True)
    document_type = fields.Selection(
        [
            ("registration", "Registration Document"),
            ("insurance", "Insurance Document"),
            ("inspection", "Inspection Certificate"),
            ("other", "Other Document"),
        ],
        string="Document Type",
        required=True,
        default="other",
    )

    document_file = fields.Binary(string="Document File", required=True)
    file_name = fields.Char(string="File Name")
    upload_date = fields.Datetime(string="Upload Date", default=fields.Datetime.now)
