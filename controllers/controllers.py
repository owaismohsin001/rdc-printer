from odoo import http
from odoo.http import request
import json


class VehicleRegistrationController(http.Controller):

    @http.route(
        "/api/vehicle/registration/<string:chassis_number>",
        type="http",
        auth="public",
        methods=["GET"],
        csrf=False,
    )
    def get_vehicle_by_chassis(self, chassis_number, **kwargs):
        """Get vehicle registration by chassis number"""
        try:
            vehicle = (
                request.env["vehicle.registration"]
                .sudo()
                .search([("chassis_number", "=", chassis_number)], limit=1)
            )

            if not vehicle:
                return request.make_response(
                    json.dumps({"error": "Vehicle not found"}),
                    headers=[("Content-Type", "application/json")],
                    status=404,
                )

            data = {
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
                "print_date": (
                    vehicle.print_date.isoformat() if vehicle.print_date else None
                ),
                "qr_code_data": vehicle.qr_code_data,
            }

            return request.make_response(
                json.dumps(data), headers=[("Content-Type", "application/json")]
            )

        except Exception as e:
            return request.make_response(
                json.dumps({"error": str(e)}),
                headers=[("Content-Type", "application/json")],
                status=500,
            )

    @http.route(
        "/api/vehicle/registrations",
        type="http",
        auth="public",
        methods=["GET"],
        csrf=False,
    )
    def get_all_vehicles(self, **kwargs):
        """Get all vehicle registrations with optional filters"""
        try:
            domain = []

            # Optional filters
            if kwargs.get("region_code"):
                domain.append(("region_code", "=", kwargs.get("region_code")))

            if kwargs.get("brand"):
                domain.append(("brand", "ilike", kwargs.get("brand")))

            vehicles = request.env["vehicle.registration"].sudo().search(domain)

            data = []
            for vehicle in vehicles:
                data.append(
                    {
                        "id": vehicle.id,
                        "chassis_number": vehicle.chassis_number,
                        "driver_name": vehicle.driver_name,
                        "brand": vehicle.brand,
                        "plate_sequence": vehicle.plate_sequence,
                        "unique_plate_number": vehicle.unique_plate_number,
                        "region_code": vehicle.region_code,
                        "print_date": (
                            vehicle.print_date.isoformat()
                            if vehicle.print_date
                            else None
                        ),
                    }
                )

            return request.make_response(
                json.dumps({"vehicles": data, "count": len(data)}),
                headers=[("Content-Type", "application/json")],
            )

        except Exception as e:
            return request.make_response(
                json.dumps({"error": str(e)}),
                headers=[("Content-Type", "application/json")],
                status=500,
            )

    @http.route(
        "/api/vehicle/reprint/<int:vehicle_id>",
        type="http",
        auth="public",
        methods=["GET"],
        csrf=False,
    )
    def reprint_vehicle(self, vehicle_id, **kwargs):
        """Trigger reprint for a vehicle (same QR code and unique number)"""
        try:
            vehicle = request.env["vehicle.registration"].sudo().browse(vehicle_id)

            if not vehicle.exists():
                return request.make_response(
                    json.dumps({"error": "Vehicle not found"}),
                    headers=[("Content-Type", "application/json")],
                    status=404,
                )

            # Mark as reprinted
            vehicle.sudo().write({"is_reprinted": True})

            # Create print history record
            request.env["vehicle.print.history"].sudo().create(
                {
                    "vehicle_id": vehicle.id,
                    "print_type": "reprint",
                    "printer_name": kwargs.get("printer_name", "Unknown"),
                    "print_status": "pending",
                }
            )

            data = {
                "message": "Reprint initiated successfully",
                "vehicle_id": vehicle.id,
                "chassis_number": vehicle.chassis_number,
                "plate_sequence": vehicle.plate_sequence,
                "unique_plate_number": vehicle.unique_plate_number,
                "qr_code_data": vehicle.qr_code_data,
            }

            return request.make_response(
                json.dumps(data), headers=[("Content-Type", "application/json")]
            )

        except Exception as e:
            return request.make_response(
                json.dumps({"error": str(e)}),
                headers=[("Content-Type", "application/json")],
                status=500,
            )

    # @http.route(
    #     "/api/vehicle/registration",
    #     type="json",
    #     auth="public",
    #     methods=["POST"],
    #     csrf=False,
    # )
    # def create_vehicle(self, **kwargs):
    #     try:
    #         vehicle = (
    #             request.env["vehicle.registration"]
    #             .sudo()
    #             .create(
    #                 {
    #                     "chassis_number": kwargs.get("chassis_number"),
    #                     "driver_name": kwargs.get("driver_name"),
    #                     "driver_address": kwargs.get("driver_address"),
    #                     "tax_number": kwargs.get("tax_number"),
    #                     "brand": kwargs.get("brand"),
    #                     "vehicle_type": kwargs.get("vehicle_type"),
    #                     "manufacturing_year": kwargs.get("manufacturing_year"),
    #                     "color": kwargs.get("color"),
    #                     "fiscal_power": kwargs.get("fiscal_power"),
    #                     "reference_number": kwargs.get("reference_number"),
    #                     "first_registration": kwargs.get("first_registration"),
    #                     "usage": kwargs.get("usage"),
    #                     "region_code": kwargs.get("region_code"),
    #                 }
    #             )
    #         )
    #         # Generate QR code after creation
    #         vehicle.generate_qr_code()
    #         return {"success": True, "id": vehicle.id, "message": "Vehicle created"}
    #     except Exception as e:
    #         return {"success": False, "error": str(e)}
    @http.route(
        "/api/vehicle/registration",
        type="http",
        auth="public",
        methods=["POST"],
        csrf=False,
    )
    def create_vehicle(self, **kwargs):
        """Create new vehicle registration"""
        try:
            # Parse JSON data from request body
            if request.httprequest.data:
                data = json.loads(request.httprequest.data.decode("utf-8"))
            else:
                return request.make_response(
                    json.dumps({"success": False, "error": "No data provided"}),
                    headers=[("Content-Type", "application/json")],
                    status=400,
                )

            # Validate required fields
            if not data.get("chassis_number"):
                return request.make_response(
                    json.dumps(
                        {"success": False, "error": "Chassis number is required"}
                    ),
                    headers=[("Content-Type", "application/json")],
                    status=400,
                )

            if not data.get("region_code"):
                return request.make_response(
                    json.dumps({"success": False, "error": "Region code is required"}),
                    headers=[("Content-Type", "application/json")],
                    status=400,
                )

            vehicle = (
                request.env["vehicle.registration"]
                .sudo()
                .create(
                    {
                        "chassis_number": data.get("chassis_number"),
                        "driver_name": data.get("driver_name"),
                        "driver_address": data.get("driver_address"),
                        "tax_number": data.get("tax_number"),
                        "brand": data.get("brand"),
                        "vehicle_type": data.get("vehicle_type"),
                        "manufacturing_year": data.get("manufacturing_year"),
                        "color": data.get("color"),
                        "fiscal_power": data.get("fiscal_power"),
                        "reference_number": data.get("reference_number"),
                        "first_registration": data.get("first_registration"),
                        "usage": data.get("usage"),
                        "region_code": data.get("region_code"),
                    }
                )
            )

            # Generate QR code after creation
            vehicle.generate_qr_code()

            # Return complete vehicle data
            response_data = {
                "success": True,
                "id": vehicle.id,
                "message": "Vehicle created successfully",
                "vehicle": {
                    "chassis_number": vehicle.chassis_number,
                    "driver_name": vehicle.driver_name,
                    "brand": vehicle.brand,
                    "plate_sequence": vehicle.plate_sequence,
                    "unique_plate_number": vehicle.unique_plate_number,
                    "region_code": vehicle.region_code,
                    "qr_code_data": vehicle.qr_code_data,
                },
            }

            return request.make_response(
                json.dumps(response_data),
                headers=[("Content-Type", "application/json")],
                status=201,
            )

        except Exception as e:
            return request.make_response(
                json.dumps({"success": False, "error": str(e)}),
                headers=[("Content-Type", "application/json")],
                status=500,
            )
