from datetime import datetime, date, timedelta
from odoo import models, fields, api
import qrcode
import base64
import json
import logging
from io import BytesIO

_logger = logging.getLogger(__name__)


class VehicleRegistration(models.Model):
    _name = "vehicle.registration"
    _description = "Vehicle Registration"
    _rec_name = "chassis_number"
    # _inherit = ["mail.thread", "mail.activity.mixin"]  # 1

    qr_code_image = fields.Binary(string="QR Code Image")
    # Unique identifier (chassis number)
    # chassis_number = fields.Char(string="Chassis Number", required=True, index=True)
    chassis_number = fields.Char(
        string="Chassis Number", required=True, index=True, tracking=True
    )  # 1

    # Add this field to VehicleRegistration
    document_ids = fields.One2many("vehicle.document", "vehicle_id", string="Documents")
    print_history_ids = fields.One2many(
        "vehicle.print.history", "vehicle_id", string="Print History"
    )  # 1

    # Driver Information
    # driver_name = fields.Char(string="Driver Name")
    driver_name = fields.Char(string="Driver Name", tracking=True)  # 1

    driver_address = fields.Text(string="Driver Address")
    tax_number = fields.Char(string="Tax Number (N° impot)")

    # Vehicle Information
    # brand = fields.Char(string="Brand (Marque)")
    brand = fields.Char(string="Brand (Marque)", tracking=True)  # 1
    vehicle_type = fields.Char(string="Vehicle Type (Genre)")
    manufacturing_year = fields.Integer(
        string="Manufacturing Year (Année de fabrication)"
    )
    color = fields.Char(string="Color")
    fiscal_power = fields.Integer(string="Fiscal Power (Puissance fiscal)")

    # Registration Information
    reference_number = fields.Char(string="Reference Number")
    first_registration = fields.Integer(string="First Registration Year")
    usage = fields.Char(string="Usage")

    # License Plate Information
    # plate_sequence = fields.Char(
    #     string="Plate Sequence", compute="_compute_plate_sequence", store=True
    # )
    # 2
    plate_sequence = fields.Char(string="Plate Sequence", readonly=True)
    unique_plate_number = fields.Char(
        string="Unique Plate Number", compute="_compute_unique_plate_number", store=True
    )
    qr_code_data = fields.Text(string="QR Code Data")

    # Printing Information
    print_location = fields.Char(string="Print Location")
    # print_date = fields.Datetime(string="Print Date", default=fields.Datetime.now)
    print_date = fields.Datetime(
        string="Print Date", default=fields.Datetime.now, tracking=True
    )  # 1
    # is_reprinted = fields.Boolean(string="Is Reprinted", default=False)
    is_reprinted = fields.Boolean(
        string="Is Reprinted", default=False, tracking=True
    )  # 1

    # Region mapping for last 2 digits of plate
    region_code = fields.Selection(
        [
            ("01", "Kinshasa"),
            ("02", "Kongo Central"),
            ("03", "Kwilu"),
            ("04", "Kwango"),
            ("05", "Mai-Ndombe"),
            ("06", "Kasai"),
            ("07", "Kasai Central"),
            ("08", "Kasai Oriental"),
            ("09", "Sankuru"),
            ("10", "Maniema"),
            ("11", "Sud-Kivu"),
            ("12", "Nord-Kivu"),
            ("13", "Ituri"),
            ("14", "Lualaba"),
            ("15", "Haut-Katanga"),
            ("16", "Tshopo"),
            ("17", "Bas-Uele"),
            ("18", "Haut-Uele"),
            ("19", "Mongala"),
            ("20", "Nord-Ubangi"),
            ("21", "Sud-Ubangi"),
            ("22", "Equateur"),
            ("23", "Tshuapa"),
            ("24", "Lomami"),
            ("25", "Haut-Lomami"),
            ("26", "Tanganyika"),
        ],
        string="Region",
        required=True,
        tracking=True,
    )

    @api.depends("region_code")
    def _compute_unique_plate_number(self):
        """Compute unique 7-digit number for license plate"""
        for record in self:
            if record.id:
                # Format as 7-digit number starting from 0000001
                record.unique_plate_number = f"{record.id:07d}"
            else:
                record.unique_plate_number = "0000000"

    # 2
    @api.depends("region_code")
    def _compute_plate_sequence(self):
        """This method is now just for display - actual generation happens in create()"""
        for record in self:
            if not record.plate_sequence and record.region_code:
                record.plate_sequence = "0000AA00"

    @api.model
    def create(self, vals):
        """Override create to ensure chassis number uniqueness"""
        # Check if chassis number already exists
        if "chassis_number" in vals:
            existing = self.search([("chassis_number", "=", vals["chassis_number"])])
            if existing:
                raise models.ValidationError(
                    f"Chassis number {vals['chassis_number']} already exists!"
                )
        # 2
        if "region_code" in vals:
            plate_number = self._generate_plate_number(vals["region_code"])
            vals["plate_sequence"] = plate_number

        return super(VehicleRegistration, self).create(vals)

    def generate_qr_code(self):
        """Generate actual QR code image"""
        for record in self:
            qr_data = {
                "chassis": record.chassis_number,
                "plate": record.plate_sequence,
                "unique_id": record.unique_plate_number,
                "driver": record.driver_name,
                "brand": record.brand,
                "year": record.manufacturing_year,
                "region": record.region_code,  # 1
                "generated_at": fields.Datetime.now().isoformat(),  # 1
            }

        _logger.info(f"Generating QR code for chassis: {record.chassis_number}")
        _logger.info(f"QR Data: {json.dumps(qr_data, indent=2)}")

        # Generate QR code
        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr.add_data(json.dumps(qr_data))
        qr.make(fit=True)

        # Create image
        img = qr.make_image(fill_color="black", back_color="white")

        # Convert to base64 for storage
        buffer = BytesIO()
        img.save(buffer, format="PNG")
        qr_image_base64 = base64.b64encode(buffer.getvalue()).decode()

        # Store both text and image
        # record.qr_code_data = json.dumps(qr_data)
        record.qr_code_data = json.dumps(qr_data, indent=2)  # 1
        record.qr_code_image = qr_image_base64

        _logger.info(f"QR code generated successfully for {record.chassis_number}")
        _logger.info(f"QR image size: {len(qr_image_base64)} characters (base64)")

        return True

    # 2
    def _generate_plate_number(self, region_code):
        """Generate next plate number for the region"""
        # Find or create sequence for this region
        sequence_obj = self.env["plate.sequence"].search(
            [("region_code", "=", region_code)]
        )

        if not sequence_obj:
            # Create new sequence starting at 0
            sequence_obj = self.env["plate.sequence"].create(
                {"region_code": region_code, "current_sequence": 0}
            )

        # Get next number (increment by 1)
        sequence_obj.current_sequence += 1
        sequence_number = sequence_obj.current_sequence

        # Calculate the letters (AA, AB, AC, ... ZZ)
        letter_position = (
            sequence_number - 1
        ) % 676  # 676 = 26 × 26 possible combinations
        first_letter = chr(65 + (letter_position // 26))  # A=65 in ASCII
        second_letter = chr(65 + (letter_position % 26))

        # Calculate 4-digit number (starts over after ZZ)
        four_digit_number = (sequence_number - 1) // 676

        # Combine everything: NNNNLLRR
        plate = f"{four_digit_number:04d}{first_letter}{second_letter}{region_code}"

        return plate

    # 3
    def action_print_carte_rose(self):
        """Generate and print Carte Rose"""
        if not self.qr_code_image:
            self.generate_qr_code()
        self.env["vehicle.print.history"].create(
            {
                "vehicle_id": self.id,
                "print_type": "carte_rose",
                "printer_name": "Authentys Pro RT1",
                "print_status": "success",
                "notes": "Carte Rose printed",
            }
        )
        return self.env.ref("rdc_printer.action_report_carte_rose").report_action(self)


# 2
class PlateSequence(models.Model):
    _name = "plate.sequence"
    _description = "Plate Number Sequence per Region"

    region_code = fields.Selection(
        [
            ("01", "Kinshasa"),
            ("02", "Kongo Central"),
            ("03", "Kwilu"),
            ("04", "Kwango"),
            ("05", "Mai-Ndombe"),
            ("06", "Kasai"),
            ("07", "Kasai Central"),
            ("08", "Kasai Oriental"),
            ("09", "Sankuru"),
            ("10", "Maniema"),
            ("11", "Sud-Kivu"),
            ("12", "Nord-Kivu"),
            ("13", "Ituri"),
            ("14", "Lualaba"),
            ("15", "Haut-Katanga"),
            ("16", "Tshopo"),
            ("17", "Bas-Uele"),
            ("18", "Haut-Uele"),
            ("19", "Mongala"),
            ("20", "Nord-Ubangi"),
            ("21", "Sud-Ubangi"),
            ("22", "Equateur"),
            ("23", "Tshuapa"),
            ("24", "Lomami"),
            ("25", "Haut-Lomami"),
            ("26", "Tanganyika"),
        ],
        string="Region",
        required=True,
    )
    current_sequence = fields.Integer(string="Current Sequence", default=0)
    _sql_constraints = [
        (
            "unique_region",
            "unique(region_code)",
            "Each region can have only one sequence!",
        )
    ]


class PrintHistory(models.Model):
    _name = "vehicle.print.history"
    _description = "Vehicle Print History"
    _order = "print_date desc"

    vehicle_id = fields.Many2one(
        "vehicle.registration", string="Vehicle", required=True, ondelete="cascade"
    )
    print_type = fields.Selection(
        [
            ("license_plate", "License Plate"),
            ("carte_rose", "Carte Rose"),
            ("reprint", "Reprint"),
        ],
        string="Print Type",
        required=True,
    )
    print_date = fields.Datetime(string="Print Date", default=fields.Datetime.now)
    printer_name = fields.Char(string="Printer Name")
    print_status = fields.Selection(
        [("success", "Success"), ("failed", "Failed"), ("pending", "Pending")],
        string="Print Status",
        default="pending",
    )
    notes = fields.Text(string="Notes")
