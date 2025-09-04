from odoo import http
import logging
from odoo.http import request
import json
import base64

_logger = logging.getLogger(__name__)


class VehicleRegistrationController(http.Controller):

    @http.route(
        "/api/vehicle/register",
        type="http",
        auth="public",
        methods=["POST"],
        csrf=False,
    )
    def register_vehicle_complete(self, **kwargs):
        """
        Single API endpoint for complete vehicle registration
        Handles: vehicle data + document uploads + QR generation + plate assignment
        """
        try:
            # Get form data and files
            chassis_number = kwargs.get("chassis_number")

            if not chassis_number:
                return self._error_response("Chassis number is required", 400)

            region_code = kwargs.get("region_code")
            if not region_code:
                return self._error_response("Region code is required", 400)

            # Check if vehicle already exists
            existing_vehicle = (
                request.env["vehicle.registration"]
                .sudo()
                .search([("chassis_number", "=", chassis_number)], limit=1)
            )

            if existing_vehicle:
                return self._error_response(
                    f"Vehicle with chassis number {chassis_number} already exists", 409
                )

            # Create vehicle record
            vehicle_data = {
                "chassis_number": chassis_number,
                "driver_name": kwargs.get("driver_name"),
                "driver_address": kwargs.get("driver_address"),
                "tax_number": kwargs.get("tax_number"),
                "brand": kwargs.get("brand"),
                "vehicle_type": kwargs.get("vehicle_type"),
                "manufacturing_year": int(kwargs.get("manufacturing_year", 0)) or None,
                "color": kwargs.get("color"),
                "fiscal_power": int(kwargs.get("fiscal_power", 0)) or None,
                "reference_number": kwargs.get("reference_number"),
                "first_registration": int(kwargs.get("first_registration", 0)) or None,
                "usage": kwargs.get("usage"),
                "region_code": region_code,
            }

            # Remove None values
            vehicle_data = {k: v for k, v in vehicle_data.items() if v is not None}

            # Create the vehicle
            vehicle = request.env["vehicle.registration"].sudo().create(vehicle_data)

            # Generate QR code and plate numbers automatically
            vehicle.generate_qr_code()

            # Handle document uploads
            uploaded_documents = []
            files = request.httprequest.files

            for file_key in files:
                uploaded_file = files[file_key]
                if uploaded_file and uploaded_file.filename:

                    # Determine document type from form data or filename
                    doc_type = kwargs.get(f"{file_key}_type", "other")
                    doc_name = kwargs.get(f"{file_key}_name", uploaded_file.filename)

                    # Create document record
                    document = (
                        request.env["vehicle.document"]
                        .sudo()
                        .create(
                            {
                                "vehicle_id": vehicle.id,
                                "document_name": doc_name,
                                "document_type": doc_type,
                                "document_file": base64.b64encode(uploaded_file.read()),
                                "file_name": uploaded_file.filename,
                            }
                        )
                    )

                    uploaded_documents.append(
                        {
                            "id": document.id,
                            "name": doc_name,
                            "type": doc_type,
                            "filename": uploaded_file.filename,
                        }
                    )

            # Create initial print history record
            request.env["vehicle.print.history"].sudo().create(
                {
                    "vehicle_id": vehicle.id,
                    "print_type": "license_plate",
                    "printer_name": kwargs.get("printer_name", "Default"),
                    "print_status": "pending",
                    "notes": "Initial registration",
                }
            )

            # Return complete response
            response_data = {
                "success": True,
                "message": "Vehicle registered successfully",
                "vehicle": {
                    "id": vehicle.id,
                    "chassis_number": vehicle.chassis_number,
                    "driver_name": vehicle.driver_name,
                    "brand": vehicle.brand,
                    "vehicle_type": vehicle.vehicle_type,
                    "manufacturing_year": vehicle.manufacturing_year,
                    "color": vehicle.color,
                    "region_code": vehicle.region_code,
                    "plate_sequence": vehicle.plate_sequence,
                    "unique_plate_number": vehicle.unique_plate_number,
                    "qr_code_data": vehicle.qr_code_data,
                    "print_date": (
                        vehicle.print_date.isoformat() if vehicle.print_date else None
                    ),
                },
                "documents": uploaded_documents,
                "documents_count": len(uploaded_documents),
            }

            return request.make_response(
                json.dumps(response_data),
                headers=[("Content-Type", "application/json")],
                status=201,
            )

        except ValueError as ve:
            return self._error_response(f"Invalid data: {str(ve)}", 400)
        except Exception as e:
            return self._error_response(f"Registration failed: {str(e)}", 500)

    @http.route(
        "/api/vehicle/<string:chassis_number>",
        type="http",
        auth="public",
        methods=["GET"],
        csrf=False,
    )
    def get_vehicle_complete(self, chassis_number, **kwargs):
        """Get complete vehicle information including documents and history"""
        try:
            vehicle = (
                request.env["vehicle.registration"]
                .sudo()
                .search([("chassis_number", "=", chassis_number)], limit=1)
            )

            if not vehicle:
                return self._error_response("Vehicle not found", 404)

            # Get documents
            documents = []
            for doc in vehicle.document_ids:
                documents.append(
                    {
                        "id": doc.id,
                        "name": doc.document_name,
                        "type": doc.document_type,
                        "filename": doc.file_name,
                        "upload_date": (
                            doc.upload_date.isoformat() if doc.upload_date else None
                        ),
                    }
                )

            # Get print history
            print_history = []
            history_records = (
                request.env["vehicle.print.history"]
                .sudo()
                .search([("vehicle_id", "=", vehicle.id)], order="print_date desc")
            )

            for history in history_records:
                print_history.append(
                    {
                        "print_type": history.print_type,
                        "print_date": (
                            history.print_date.isoformat()
                            if history.print_date
                            else None
                        ),
                        "printer_name": history.printer_name,
                        "status": history.print_status,
                        "notes": history.notes,
                    }
                )

            data = {
                "success": True,
                "vehicle": {
                    "id": vehicle.id,
                    "chassis_number": vehicle.chassis_number,
                    "driver_name": vehicle.driver_name,
                    "driver_address": vehicle.driver_address,
                    "tax_number": vehicle.tax_number,
                    "brand": vehicle.brand,
                    "vehicle_type": vehicle.vehicle_type,
                    "manufacturing_year": vehicle.manufacturing_year,
                    "color": vehicle.color,
                    "fiscal_power": vehicle.fiscal_power,
                    "reference_number": vehicle.reference_number,
                    "first_registration": vehicle.first_registration,
                    "usage": vehicle.usage,
                    "plate_sequence": vehicle.plate_sequence,
                    "unique_plate_number": vehicle.unique_plate_number,
                    "region_code": vehicle.region_code,
                    "qr_code_data": vehicle.qr_code_data,
                    "print_date": (
                        vehicle.print_date.isoformat() if vehicle.print_date else None
                    ),
                    "is_reprinted": vehicle.is_reprinted,
                },
                "documents": documents,
                "print_history": print_history,
                "counts": {"documents": len(documents), "prints": len(print_history)},
            }

            return request.make_response(
                json.dumps(data), headers=[("Content-Type", "application/json")]
            )

        except Exception as e:
            return self._error_response(str(e), 500)

    def _create_or_update_vehicle(self, chassis_number, create_new=True):
        """Create new vehicle or update existing one"""
        try:
            # Check if vehicle exists
            existing_vehicle = (
                request.env["vehicle.registration"]
                .sudo()
                .search([("chassis_number", "=", chassis_number)], limit=1)
            )

            if create_new and existing_vehicle:
                return self._error_response(
                    f"Vehicle with chassis number {chassis_number} already exists", 409
                )

            if not create_new and not existing_vehicle:
                return self._error_response("Vehicle not found for update", 404)

            # Get form data
            vehicle_data = {
                "chassis_number": chassis_number,
                "driver_name": request.params.get("driver_name"),
                "driver_address": request.params.get("driver_address"),
                "tax_number": request.params.get("tax_number"),
                "brand": request.params.get("brand"),
                "vehicle_type": request.params.get("vehicle_type"),
                "manufacturing_year": self._safe_int(
                    request.params.get("manufacturing_year")
                ),
                "color": request.params.get("color"),
                "fiscal_power": self._safe_int(request.params.get("fiscal_power")),
                "reference_number": request.params.get("reference_number"),
                "first_registration": self._safe_int(
                    request.params.get("first_registration")
                ),
                "usage": request.params.get("usage"),
                "region_code": request.params.get("region_code"),
            }

            # Remove None values
            vehicle_data = {k: v for k, v in vehicle_data.items() if v is not None}

            if create_new:
                vehicle = (
                    request.env["vehicle.registration"].sudo().create(vehicle_data)
                )
                action = "created"
            else:
                existing_vehicle.sudo().write(vehicle_data)
                vehicle = existing_vehicle
                action = "updated"

            # Generate/regenerate QR code
            vehicle.generate_qr_code()

            # Handle document uploads
            uploaded_documents = []
            files = request.httprequest.files

            for file_key in files:
                uploaded_file = files[file_key]
                if uploaded_file and uploaded_file.filename:

                    # Get document metadata from form
                    doc_type = request.params.get(f"{file_key}_type", "other")
                    doc_name = request.params.get(
                        f"{file_key}_name", uploaded_file.filename
                    )

                    # Create document record
                    document = (
                        request.env["vehicle.document"]
                        .sudo()
                        .create(
                            {
                                "vehicle_id": vehicle.id,
                                "document_name": doc_name,
                                "document_type": doc_type,
                                "document_file": base64.b64encode(uploaded_file.read()),
                                "file_name": uploaded_file.filename,
                            }
                        )
                    )

                    uploaded_documents.append(
                        {
                            "id": document.id,
                            "name": doc_name,
                            "type": doc_type,
                            "filename": uploaded_file.filename,
                        }
                    )

            # Create print history if new registration
            if create_new:
                request.env["vehicle.print.history"].sudo().create(
                    {
                        "vehicle_id": vehicle.id,
                        "print_type": "license_plate",
                        "printer_name": request.params.get("printer_name", "Default"),
                        "print_status": "pending",
                        "notes": f"Initial registration - {action}",
                    }
                )

            # Return complete response
            response_data = {
                "success": True,
                "message": f"Vehicle {action} successfully",
                "action": action,
                "vehicle": {
                    "id": vehicle.id,
                    "chassis_number": vehicle.chassis_number,
                    "driver_name": vehicle.driver_name,
                    "brand": vehicle.brand,
                    "vehicle_type": vehicle.vehicle_type,
                    "manufacturing_year": vehicle.manufacturing_year,
                    "color": vehicle.color,
                    "region_code": vehicle.region_code,
                    "plate_sequence": vehicle.plate_sequence,
                    "unique_plate_number": vehicle.unique_plate_number,
                    "qr_code_data": vehicle.qr_code_data,
                    "print_date": (
                        vehicle.print_date.isoformat() if vehicle.print_date else None
                    ),
                },
                "documents": uploaded_documents,
                "documents_count": len(uploaded_documents),
            }

            return request.make_response(
                json.dumps(response_data),
                headers=[("Content-Type", "application/json")],
                status=201 if create_new else 200,
            )

        except Exception as e:
            return self._error_response(f"Operation failed: {str(e)}", 500)

    @http.route(
        "/api/vehicle/reprint/<string:chassis_number>",
        type="http",
        auth="public",
        methods=["POST"],
        csrf=False,
    )
    def reprint_vehicle_by_chassis(self, chassis_number, **kwargs):
        """Trigger reprint using chassis number instead of vehicle ID"""
        try:
            vehicle = (
                request.env["vehicle.registration"]
                .sudo()
                .search([("chassis_number", "=", chassis_number)], limit=1)
            )

            if not vehicle:
                return self._error_response("Vehicle not found", 404)

            # Mark as reprinted
            vehicle.sudo().write({"is_reprinted": True})

            # Create print history record
            request.env["vehicle.print.history"].sudo().create(
                {
                    "vehicle_id": vehicle.id,
                    "print_type": "reprint",
                    "printer_name": request.params.get("printer_name", "Unknown"),
                    "print_status": "pending",
                    "notes": "Reprint requested",
                }
            )

            data = {
                "success": True,
                "message": "Reprint initiated successfully",
                "vehicle": {
                    "id": vehicle.id,
                    "chassis_number": vehicle.chassis_number,
                    "plate_sequence": vehicle.plate_sequence,
                    "unique_plate_number": vehicle.unique_plate_number,
                    "qr_code_data": vehicle.qr_code_data,
                    "driver_name": vehicle.driver_name,
                    "brand": vehicle.brand,
                },
            }

            return request.make_response(
                json.dumps(data), headers=[("Content-Type", "application/json")]
            )

        except Exception as e:
            return self._error_response(str(e), 500)

    @http.route(
        "/api/vehicle/search",
        type="http",
        auth="public",
        methods=["GET"],
        csrf=False,
    )
    def search_vehicles(self, **kwargs):
        """Search vehicles with multiple criteria"""
        try:
            domain = []

            # Search by chassis number (exact or partial)
            if kwargs.get("chassis_number"):
                chassis = kwargs.get("chassis_number")
                if kwargs.get("exact_match", "false").lower() == "true":
                    domain.append(("chassis_number", "=", chassis))
                else:
                    domain.append(("chassis_number", "ilike", chassis))

            # Search by driver name
            if kwargs.get("driver_name"):
                domain.append(("driver_name", "ilike", kwargs.get("driver_name")))

            # Filter by region
            if kwargs.get("region_code"):
                domain.append(("region_code", "=", kwargs.get("region_code")))

            # Filter by brand
            if kwargs.get("brand"):
                domain.append(("brand", "ilike", kwargs.get("brand")))

            # Filter by plate sequence
            if kwargs.get("plate_sequence"):
                domain.append(("plate_sequence", "ilike", kwargs.get("plate_sequence")))

            # Pagination
            limit = int(kwargs.get("limit", 50))
            offset = int(kwargs.get("offset", 0))

            vehicles = (
                request.env["vehicle.registration"]
                .sudo()
                .search(domain, limit=limit, offset=offset, order="create_date desc")
            )
            total_count = (
                request.env["vehicle.registration"].sudo().search_count(domain)
            )

            results = []
            for vehicle in vehicles:
                results.append(
                    {
                        "id": vehicle.id,
                        "chassis_number": vehicle.chassis_number,
                        "driver_name": vehicle.driver_name,
                        "brand": vehicle.brand,
                        "vehicle_type": vehicle.vehicle_type,
                        "plate_sequence": vehicle.plate_sequence,
                        "unique_plate_number": vehicle.unique_plate_number,
                        "region_code": vehicle.region_code,
                        "print_date": (
                            vehicle.print_date.isoformat()
                            if vehicle.print_date
                            else None
                        ),
                        "is_reprinted": vehicle.is_reprinted,
                        "documents_count": len(vehicle.document_ids),
                    }
                )

            return request.make_response(
                json.dumps(
                    {
                        "success": True,
                        "vehicles": results,
                        "pagination": {
                            "total": total_count,
                            "limit": limit,
                            "offset": offset,
                            "returned": len(results),
                        },
                    }
                ),
                headers=[("Content-Type", "application/json")],
            )

        except Exception as e:
            return self._error_response(str(e), 500)

    @http.route(
        "/api/vehicle/document/<int:document_id>/download",
        type="http",
        auth="public",
        methods=["GET"],
        csrf=False,
    )
    def download_document(self, document_id, **kwargs):
        """Download a specific document"""
        try:
            document = request.env["vehicle.document"].sudo().browse(document_id)

            if not document.exists():
                return self._error_response("Document not found", 404)

            # Decode the file
            file_data = base64.b64decode(document.document_file)

            # Return file response
            return request.make_response(
                file_data,
                headers=[
                    ("Content-Type", "application/octet-stream"),
                    (
                        "Content-Disposition",
                        f'attachment; filename="{document.file_name}"',
                    ),
                ],
            )

        except Exception as e:
            return self._error_response(str(e), 500)

    def _error_response(self, message, status_code):
        """Helper method to create consistent error responses"""
        return request.make_response(
            json.dumps({"success": False, "error": message}),
            headers=[("Content-Type", "application/json")],
            status=status_code,
        )

    def _safe_int(self, value):
        """Safely convert value to integer"""
        if not value:
            return None
        try:
            return int(value)
        except (ValueError, TypeError):
            return None

    # 3
    @http.route(
        "/api/vehicle/carte_rose/<string:chassis_number>",
        type="http",
        auth="public",
        methods=["GET"],
        csrf=False,
    )
    def get_carte_rose_pdf(self, chassis_number, **kwargs):
        """Generate Carte Rose PDF via API"""
        try:
            vehicle = (
                request.env["vehicle.registration"]
                .sudo()
                .search([("chassis_number", "=", chassis_number)], limit=1)
            )

            if not vehicle:
                return self._error_response("Vehicle not found", 404)

            # Generate QR code if not exists
            if not vehicle.qr_code_image:
                vehicle.generate_qr_code()

            # Generate PDF
            # report = request.env.ref("rdc_printer.action_report_carte_rose").sudo()
            # pdf, _ = report._render_qweb_pdf(vehicle.id)
            report = request.env.ref("rdc_printer.action_report_carte_rose").sudo()
            pdf, _ = report._render_qweb_pdf(vehicle.id)

            # Create print history
            request.env["vehicle.print.history"].sudo().create(
                {
                    "vehicle_id": vehicle.id,
                    "print_type": "carte_rose",
                    "printer_name": "Authentys Pro RT1",
                    "print_status": "success",
                    "notes": "Carte Rose generated via API",
                }
            )

            return request.make_response(
                pdf,
                headers=[
                    ("Content-Type", "application/pdf"),
                    (
                        "Content-Disposition",
                        f'attachment; filename="carte_rose_{chassis_number}.pdf"',
                    ),
                ],
            )

        except Exception as e:
            return self._error_response(str(e), 500)
