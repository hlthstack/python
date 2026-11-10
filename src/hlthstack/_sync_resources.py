# This file is generated from _async_resources.py by scripts/unasync.py. Do not edit.
"""API operations, grouped by area.

``_async_resources.py`` is the single source for both clients: ``_sync_resources.py`` is
generated from it. Edit the async file, then run ``python scripts/unasync.py``.

Every method accepts ``entity_id=`` and ``secret_key=`` to act for another entity on that
call (multi-entity partners); they default to the client's settings. The pre-registration
methods are the exception: they use their own token and name the company in each row.

Every method that calls the API also accepts ``validate=`` to turn client-side request
validation on or off for that call; it defaults to the client's ``validate`` setting.
"""

from collections.abc import Mapping, Sequence
from typing import TYPE_CHECKING, Literal, Optional, Union, cast

from ._base_client import (
    Date,
    DateTime,
    FileInput,
    PackageIds,
    Part,
    compact,
    coordinate,
    datetime_utc,
    file_part,
    file_parts,
    join_ids,
    path,
    query,
    text_part,
)
from .types import (
    AppointmentPaymentDetailsResponse,
    AppointmentReportsResponse,
    AppointmentSimulationStatus,
    AppointmentType,
    BookingAddress,
    BookingCustomer,
    BookingDetails,
    CancelOrderResponse,
    CartCustomerDetails,
    CartProductInput,
    CartResponse,
    ConfirmOrderResponse,
    ConsultationCancelResponse,
    ConsultationCustomer,
    ConsultationDetails,
    ConsultationSimulationStatus,
    CreateAppointmentResponse,
    CreateConsultationResponse,
    CreateOrderResponse,
    CustomerAppointmentsResponse,
    CustomerPlansResponse,
    DeliveryOption,
    DigitizationAccepted,
    DigitizationCustomer,
    DigitizationStatus,
    FulfillmentOptions,
    LabResults,
    MedicineSearchResponse,
    MessageResponse,
    MessagesResponse,
    OrderList,
    OrderPaymentDetails,
    OrderResponse,
    PartialResult,
    PaymentDetailsCustomer,
    PharmacyAddress,
    PreRegistrationAccepted,
    PreRegistrationAccessToken,
    PreRegistrationDependant,
    PreRegistrationDependantUpdate,
    PreRegistrationEmployee,
    PreRegistrationEmployeeUpdate,
    PreRegistrationStatus,
    ProvidersResponse,
    SimulateOrderStatusResponse,
    SlotsResponse,
    SummaryAndPrescription,
    WalletResponse,
)

if TYPE_CHECKING:
    from ._client import Hlthstack

__all__ = [
    "Appointments",
    "Consultations",
    "Pharmacy",
    "PreRegistration",
    "Testing",
    "Wallet",
]

SortBy = Literal["fee", "experience", "distance", "rating", "visited_before"]
DoctorGender = Literal["Male", "Female", "Non-binary"]


class _Resource:
    def __init__(self, client: "Hlthstack") -> None:
        self._client = client


class _Slots(_Resource):
    def list_slots(
        self,
        provider_id: Union[int, str],
        benefit_type: str,
        *,
        package_ids: PackageIds,
        booking_date: Optional[Date] = None,
        count_days: Optional[int] = None,
        slot_start_date: Optional[Date] = None,
        pincode: Optional[str] = None,
        latitude: Optional[float] = None,
        longitude: Optional[float] = None,
        city_name: Optional[str] = None,
        plan_id: Optional[str] = None,
        entity_id: Optional[str] = None,
        secret_key: Optional[str] = None,
        validate: Optional[bool] = None,
    ) -> SlotsResponse:
        """List bookable slots for one provider (``listSlots``).

        ``GET /api/providers/{provider_id}/{benefit_type}/slots``. ``benefit_type`` takes the
        same values as ``service_name`` (``ahc``, ``inclinic_consultation``,
        ``specialist_consultation``, ...). Pass ``booking_date`` for one day, or omit it
        for several days (``count_days``, default 14). Read ``booking_slots``.
        """
        return cast(
            SlotsResponse,
            self._client._request(
                "GET",
                path("/api/providers/{}/{}/slots", provider_id, benefit_type),
                operation="listSlots",
                validate=validate,
                params=query(
                    {
                        "package_ids": join_ids(package_ids),
                        "booking_date": booking_date,
                        "count_days": count_days,
                        "slot_start_date": slot_start_date,
                        "pincode": pincode,
                        "latitude": coordinate(latitude),
                        "longitude": coordinate(longitude),
                        "city_name": city_name,
                        "plan_id": plan_id,
                    }
                ),
                entity_id=entity_id,
                secret_key=secret_key,
            ),
        )


class Appointments(_Slots):
    """Health checkups, lab tests, dental, vision and vaccinations."""

    def list_providers(
        self,
        *,
        service_name: str,
        package_ids: PackageIds,
        pincode: Optional[str] = None,
        latitude: Optional[float] = None,
        longitude: Optional[float] = None,
        radius: Optional[float] = None,
        auto_allocate_provider: Optional[bool] = None,
        plan_id: Optional[str] = None,
        page: Optional[int] = None,
        per_page: Optional[int] = None,
        sort_by: Optional[SortBy] = None,
        sort_asc: Optional[bool] = None,
        gender: Optional[DoctorGender] = None,
        api_customer_id: Optional[str] = None,
        entity_id: Optional[str] = None,
        secret_key: Optional[str] = None,
        validate: Optional[bool] = None,
    ) -> ProvidersResponse:
        """Find providers for a service and packages near a location (``listProviders``).

        ``GET /api/providers``. Send ``pincode`` or ``latitude`` + ``longitude``.
        ``package_ids`` may be a list or a comma-separated string.
        """
        return cast(
            ProvidersResponse,
            self._client._request(
                "GET",
                "/api/providers",
                operation="listProviders",
                validate=validate,
                params=query(
                    {
                        "service_name": service_name,
                        "package_ids": join_ids(package_ids),
                        "pincode": pincode,
                        "latitude": coordinate(latitude),
                        "longitude": coordinate(longitude),
                        "radius": radius,
                        "auto_allocate_provider": auto_allocate_provider,
                        "plan_id": plan_id,
                        "page": page,
                        "per_page": per_page,
                        "sort_by": sort_by,
                        "sort_asc": sort_asc,
                        "gender": gender,
                        "api_customer_id": api_customer_id,
                    }
                ),
                entity_id=entity_id,
                secret_key=secret_key,
            ),
        )

    def create(
        self,
        *,
        service_name: str,
        appointment_type: AppointmentType,
        provider_id: Union[int, str],
        appointment_date_time: DateTime,
        customers: Sequence[BookingCustomer],
        address: Optional[BookingAddress] = None,
        plan_id: Optional[str] = None,
        customer_plan_id: Optional[int] = None,
        subscription_id: Optional[str] = None,
        api_partner_order_id: Optional[str] = None,
        entity_id: Optional[str] = None,
        secret_key: Optional[str] = None,
        validate: Optional[bool] = None,
    ) -> CreateAppointmentResponse:
        """Book an appointment for one or more members (``createAppointment``).

        ``POST /api/appointments``. Use a slot's ``utc_slot_time`` as
        ``appointment_date_time`` (a string, or a timezone-aware ``datetime``). Don't retry
        blindly on failure: check ``get`` or your webhooks first.
        """
        return cast(
            CreateAppointmentResponse,
            self._client._request(
                "POST",
                "/api/appointments",
                operation="createAppointment",
                validate=validate,
                json=compact(
                    {
                        "service_name": service_name,
                        "appointment_type": appointment_type,
                        "provider_id": provider_id,
                        "appointment_date_time": datetime_utc(appointment_date_time),
                        "customers": list(customers),
                        "address": address,
                        "plan_id": plan_id,
                        "customer_plan_id": customer_plan_id,
                        "subscription_id": subscription_id,
                        "api_partner_order_id": api_partner_order_id,
                    }
                ),
                entity_id=entity_id,
                secret_key=secret_key,
            ),
        )

    def get(
        self,
        booking_id: str,
        *,
        appointment_id: Optional[str] = None,
        entity_id: Optional[str] = None,
        secret_key: Optional[str] = None,
        validate: Optional[bool] = None,
    ) -> BookingDetails:
        """Get a booking, or one appointment in it (``getAppointment``).

        ``GET /api/appointments``.
        """
        return cast(
            BookingDetails,
            self._client._request(
                "GET",
                "/api/appointments",
                operation="getAppointment",
                validate=validate,
                params=query({"booking_id": booking_id, "appointment_id": appointment_id}),
                entity_id=entity_id,
                secret_key=secret_key,
            ),
        )

    def list_customer_appointments(
        self,
        *,
        api_customer_id: Optional[str] = None,
        employee_id: Optional[str] = None,
        from_date: Optional[Date] = None,
        to_date: Optional[Date] = None,
        status: Optional[str] = None,
        entity_id: Optional[str] = None,
        secret_key: Optional[str] = None,
        validate: Optional[bool] = None,
    ) -> CustomerAppointmentsResponse:
        """List a member's appointments (``listCustomerAppointments``).

        ``GET /api/appointments/customer_appointments``.
        """
        return cast(
            CustomerAppointmentsResponse,
            self._client._request(
                "GET",
                "/api/appointments/customer_appointments",
                operation="listCustomerAppointments",
                validate=validate,
                params=query(
                    {
                        "api_customer_id": api_customer_id,
                        "employee_id": employee_id,
                        "from_date": from_date,
                        "to_date": to_date,
                        "status": status,
                    }
                ),
                entity_id=entity_id,
                secret_key=secret_key,
            ),
        )

    def get_payment_details(
        self,
        *,
        provider_id: int,
        appointment_type: AppointmentType,
        service_name: str,
        customers: Sequence[PaymentDetailsCustomer],
        plan_id: Optional[str] = None,
        customer_plan_id: Optional[int] = None,
        subscription_id: Optional[str] = None,
        entity_id: Optional[str] = None,
        secret_key: Optional[str] = None,
        validate: Optional[bool] = None,
    ) -> AppointmentPaymentDetailsResponse:
        """Price a booking before creating it (``getAppointmentPaymentDetails``).

        ``POST /api/appointments/payment_details``.
        """
        return cast(
            AppointmentPaymentDetailsResponse,
            self._client._request(
                "POST",
                "/api/appointments/payment_details",
                operation="getAppointmentPaymentDetails",
                validate=validate,
                json=compact(
                    {
                        "provider_id": provider_id,
                        "appointment_type": appointment_type,
                        "service_name": service_name,
                        "customers": list(customers),
                        "plan_id": plan_id,
                        "customer_plan_id": customer_plan_id,
                        "subscription_id": subscription_id,
                    }
                ),
                entity_id=entity_id,
                secret_key=secret_key,
            ),
        )

    def reschedule_booking(
        self,
        booking_id: str,
        *,
        appointment_date_time: DateTime,
        provider_id: Union[int, str, None] = None,
        address: Optional[BookingAddress] = None,
        entity_id: Optional[str] = None,
        secret_key: Optional[str] = None,
        validate: Optional[bool] = None,
    ) -> PartialResult:
        """Reschedule every appointment in a booking (``rescheduleBooking``).

        ``PATCH /api/bookings/{booking_id}/reschedule``. May partially succeed: check
        ``success`` and ``failed`` (comma-separated appointment ids).
        """
        return cast(
            PartialResult,
            self._client._request(
                "PATCH",
                path("/api/bookings/{}/reschedule", booking_id),
                operation="rescheduleBooking",
                validate=validate,
                json=compact(
                    {
                        "appointment_date_time": datetime_utc(appointment_date_time),
                        "provider_id": provider_id,
                        "address": address,
                    }
                ),
                entity_id=entity_id,
                secret_key=secret_key,
            ),
        )

    def cancel_booking(
        self,
        booking_id: str,
        *,
        entity_id: Optional[str] = None,
        secret_key: Optional[str] = None,
        validate: Optional[bool] = None,
    ) -> PartialResult:
        """Cancel every appointment in a booking (``cancelBooking``).

        ``PATCH /api/bookings/{booking_id}/cancel``. May partially succeed.
        """
        return cast(
            PartialResult,
            self._client._request(
                "PATCH",
                path("/api/bookings/{}/cancel", booking_id),
                operation="cancelBooking",
                validate=validate,
                entity_id=entity_id,
                secret_key=secret_key,
            ),
        )

    def reschedule(
        self,
        appointment_id: str,
        *,
        appointment_date_time: DateTime,
        provider_id: Union[int, str, None] = None,
        address: Optional[BookingAddress] = None,
        entity_id: Optional[str] = None,
        secret_key: Optional[str] = None,
        validate: Optional[bool] = None,
    ) -> MessageResponse:
        """Reschedule one appointment (``rescheduleAppointment``).

        ``PATCH /api/appointments/{appointment_id}/reschedule``.
        """
        return cast(
            MessageResponse,
            self._client._request(
                "PATCH",
                path("/api/appointments/{}/reschedule", appointment_id),
                operation="rescheduleAppointment",
                validate=validate,
                json=compact(
                    {
                        "appointment_date_time": datetime_utc(appointment_date_time),
                        "provider_id": provider_id,
                        "address": address,
                    }
                ),
                entity_id=entity_id,
                secret_key=secret_key,
            ),
        )

    def cancel(
        self,
        appointment_id: str,
        *,
        entity_id: Optional[str] = None,
        secret_key: Optional[str] = None,
        validate: Optional[bool] = None,
    ) -> MessageResponse:
        """Cancel one appointment (``cancelAppointment``).

        ``PATCH /api/appointments/{appointment_id}/cancel``.
        """
        return cast(
            MessageResponse,
            self._client._request(
                "PATCH",
                path("/api/appointments/{}/cancel", appointment_id),
                operation="cancelAppointment",
                validate=validate,
                entity_id=entity_id,
                secret_key=secret_key,
            ),
        )

    def get_voucher(
        self,
        appointment_id: str,
        *,
        entity_id: Optional[str] = None,
        secret_key: Optional[str] = None,
        validate: Optional[bool] = None,
    ) -> bytes:
        """Download the appointment voucher PDF (``getAppointmentVoucher``).

        ``GET /api/appointments/{appointment_id}/voucher``. Returns the PDF bytes.
        """
        return cast(
            bytes,
            self._client._request(
                "GET",
                path("/api/appointments/{}/voucher", appointment_id),
                operation="getAppointmentVoucher",
                validate=validate,
                entity_id=entity_id,
                secret_key=secret_key,
                binary=True,
            ),
        )

    def get_reports(
        self,
        appointment_id: str,
        *,
        entity_id: Optional[str] = None,
        secret_key: Optional[str] = None,
        validate: Optional[bool] = None,
    ) -> AppointmentReportsResponse:
        """Get report links (``getAppointmentReports``).

        ``GET /api/appointments/{appointment_id}/reports``.
        """
        return cast(
            AppointmentReportsResponse,
            self._client._request(
                "GET",
                path("/api/appointments/{}/reports", appointment_id),
                operation="getAppointmentReports",
                validate=validate,
                entity_id=entity_id,
                secret_key=secret_key,
            ),
        )

    def get_lab_results(
        self,
        appointment_id: str,
        *,
        entity_id: Optional[str] = None,
        secret_key: Optional[str] = None,
        validate: Optional[bool] = None,
    ) -> LabResults:
        """Get digitized lab results (``getAppointmentLabResults``).

        ``GET /api/appointments/{appointment_id}/lab_results``. Must be enabled for you.
        """
        return cast(
            LabResults,
            self._client._request(
                "GET",
                path("/api/appointments/{}/lab_results", appointment_id),
                operation="getAppointmentLabResults",
                validate=validate,
                entity_id=entity_id,
                secret_key=secret_key,
            ),
        )


class Consultations(_Slots):
    """In-clinic consultations and online specialist consultations (scheduled and priority)."""

    def list_inclinic_providers(
        self,
        *,
        package_ids: PackageIds,
        pincode: Optional[str] = None,
        latitude: Optional[float] = None,
        longitude: Optional[float] = None,
        radius: Optional[float] = None,
        plan_id: Optional[str] = None,
        page: Optional[int] = None,
        per_page: Optional[int] = None,
        sort_by: Optional[SortBy] = None,
        sort_asc: Optional[bool] = None,
        gender: Optional[DoctorGender] = None,
        api_customer_id: Optional[str] = None,
        entity_id: Optional[str] = None,
        secret_key: Optional[str] = None,
        validate: Optional[bool] = None,
    ) -> ProvidersResponse:
        """Find in-clinic doctors (``listInclinicConsultationProviders``).

        ``GET /api/consultations/inclinic_consultation/providers``. Send ``pincode`` or
        ``latitude`` + ``longitude``. ``sort_by="visited_before"`` needs ``api_customer_id``.
        """
        return cast(
            ProvidersResponse,
            self._client._request(
                "GET",
                "/api/consultations/inclinic_consultation/providers",
                operation="listInclinicConsultationProviders",
                validate=validate,
                params=query(
                    {
                        "package_ids": join_ids(package_ids),
                        "pincode": pincode,
                        "latitude": coordinate(latitude),
                        "longitude": coordinate(longitude),
                        "radius": radius,
                        "plan_id": plan_id,
                        "page": page,
                        "per_page": per_page,
                        "sort_by": sort_by,
                        "sort_asc": sort_asc,
                        "gender": gender,
                        "api_customer_id": api_customer_id,
                    }
                ),
                entity_id=entity_id,
                secret_key=secret_key,
            ),
        )

    def list_specialist_providers(
        self,
        *,
        package_ids: PackageIds,
        default_provider: Optional[bool] = None,
        plan_id: Optional[str] = None,
        page: Optional[int] = None,
        per_page: Optional[int] = None,
        entity_id: Optional[str] = None,
        secret_key: Optional[str] = None,
        validate: Optional[bool] = None,
    ) -> ProvidersResponse:
        """Find online specialists (``listSpecialistConsultationProviders``).

        ``GET /api/consultations/specialist_consultation/providers``. Pass
        ``default_provider=True`` to list priority-consultation providers.
        """
        return cast(
            ProvidersResponse,
            self._client._request(
                "GET",
                "/api/consultations/specialist_consultation/providers",
                operation="listSpecialistConsultationProviders",
                validate=validate,
                params=query(
                    {
                        "package_ids": join_ids(package_ids),
                        "default_provider": default_provider,
                        "plan_id": plan_id,
                        "page": page,
                        "per_page": per_page,
                    }
                ),
                entity_id=entity_id,
                secret_key=secret_key,
            ),
        )

    def create_inclinic(
        self,
        *,
        provider_id: Union[int, str],
        appointment_date_time: DateTime,
        customers: Sequence[ConsultationCustomer],
        address: BookingAddress,
        service_mode: Optional[Literal["at_provider_location"]] = None,
        plan_id: Optional[str] = None,
        customer_plan_id: Optional[int] = None,
        subscription_id: Optional[str] = None,
        entity_id: Optional[str] = None,
        secret_key: Optional[str] = None,
        validate: Optional[bool] = None,
    ) -> CreateConsultationResponse:
        """Book an in-clinic consultation (``createInclinicConsultation``).

        ``POST /api/consultations/inclinic_consultation``. ``address`` is the member's.
        """
        return cast(
            CreateConsultationResponse,
            self._client._request(
                "POST",
                "/api/consultations/inclinic_consultation",
                operation="createInclinicConsultation",
                validate=validate,
                json=compact(
                    {
                        "appointment_date_time": datetime_utc(appointment_date_time),
                        "service_mode": service_mode,
                        "provider_id": provider_id,
                        "customers": list(customers),
                        "address": address,
                        "plan_id": plan_id,
                        "customer_plan_id": customer_plan_id,
                        "subscription_id": subscription_id,
                    }
                ),
                entity_id=entity_id,
                secret_key=secret_key,
            ),
        )

    def create_specialist(
        self,
        *,
        provider_id: Union[int, str],
        customers: Sequence[ConsultationCustomer],
        appointment_date_time: Optional[DateTime] = None,
        service_mode: Optional[Literal["audio_call", "video_call"]] = None,
        priority_consultation: Optional[bool] = None,
        plan_id: Optional[str] = None,
        customer_plan_id: Optional[int] = None,
        subscription_id: Optional[str] = None,
        entity_id: Optional[str] = None,
        secret_key: Optional[str] = None,
        validate: Optional[bool] = None,
    ) -> CreateConsultationResponse:
        """Book an online specialist consultation (``createSpecialistConsultation``).

        ``POST /api/consultations/specialist_consultation``. For a priority consultation pass
        ``priority_consultation=True`` (``appointment_date_time`` is then optional).
        """
        return cast(
            CreateConsultationResponse,
            self._client._request(
                "POST",
                "/api/consultations/specialist_consultation",
                operation="createSpecialistConsultation",
                validate=validate,
                json=compact(
                    {
                        "appointment_date_time": datetime_utc(appointment_date_time),
                        "service_mode": service_mode,
                        "priority_consultation": priority_consultation,
                        "provider_id": provider_id,
                        "customers": list(customers),
                        "plan_id": plan_id,
                        "customer_plan_id": customer_plan_id,
                        "subscription_id": subscription_id,
                    }
                ),
                entity_id=entity_id,
                secret_key=secret_key,
            ),
        )

    def get_inclinic(
        self,
        appointment_id: str,
        *,
        entity_id: Optional[str] = None,
        secret_key: Optional[str] = None,
        validate: Optional[bool] = None,
    ) -> ConsultationDetails:
        """Get an in-clinic consultation (``getInclinicConsultation``).

        ``GET /api/consultations/inclinic_consultation/{appointment_id}``.
        """
        return cast(
            ConsultationDetails,
            self._client._request(
                "GET",
                path("/api/consultations/inclinic_consultation/{}", appointment_id),
                operation="getInclinicConsultation",
                validate=validate,
                entity_id=entity_id,
                secret_key=secret_key,
            ),
        )

    def get_specialist(
        self,
        appointment_id: str,
        *,
        entity_id: Optional[str] = None,
        secret_key: Optional[str] = None,
        validate: Optional[bool] = None,
    ) -> ConsultationDetails:
        """Get an online specialist consultation (``getSpecialistConsultation``).

        ``GET /api/consultations/specialist_consultation/{appointment_id}``.
        """
        return cast(
            ConsultationDetails,
            self._client._request(
                "GET",
                path("/api/consultations/specialist_consultation/{}", appointment_id),
                operation="getSpecialistConsultation",
                validate=validate,
                entity_id=entity_id,
                secret_key=secret_key,
            ),
        )

    def reschedule(
        self,
        appointment_id: str,
        *,
        appointment_date_time: DateTime,
        entity_id: Optional[str] = None,
        secret_key: Optional[str] = None,
        validate: Optional[bool] = None,
    ) -> MessageResponse:
        """Reschedule a consultation with the same doctor (``rescheduleConsultation``).

        ``PATCH /api/consultations/{appointment_id}/reschedule``.
        """
        return cast(
            MessageResponse,
            self._client._request(
                "PATCH",
                path("/api/consultations/{}/reschedule", appointment_id),
                operation="rescheduleConsultation",
                validate=validate,
                json={"appointment_date_time": datetime_utc(appointment_date_time)},
                entity_id=entity_id,
                secret_key=secret_key,
            ),
        )

    def cancel(
        self,
        appointment_id: str,
        *,
        entity_id: Optional[str] = None,
        secret_key: Optional[str] = None,
        validate: Optional[bool] = None,
    ) -> ConsultationCancelResponse:
        """Cancel a consultation (``cancelConsultation``).

        ``PATCH /api/consultations/{appointment_id}/cancel``. Success is ``{"msg": ...}``.
        """
        return cast(
            ConsultationCancelResponse,
            self._client._request(
                "PATCH",
                path("/api/consultations/{}/cancel", appointment_id),
                operation="cancelConsultation",
                validate=validate,
                entity_id=entity_id,
                secret_key=secret_key,
            ),
        )

    def get_summary_and_prescription(
        self,
        appointment_id: str,
        *,
        entity_id: Optional[str] = None,
        secret_key: Optional[str] = None,
        validate: Optional[bool] = None,
    ) -> SummaryAndPrescription:
        """Get the consultation summary and prescriptions
        (``getConsultationSummaryAndPrescription``).

        ``GET /api/consultations/{appointment_id}/summary_and_prescription``.
        """
        return cast(
            SummaryAndPrescription,
            self._client._request(
                "GET",
                path("/api/consultations/{}/summary_and_prescription", appointment_id),
                operation="getConsultationSummaryAndPrescription",
                validate=validate,
                entity_id=entity_id,
                secret_key=secret_key,
            ),
        )

    def get_voucher(
        self,
        appointment_id: str,
        *,
        entity_id: Optional[str] = None,
        secret_key: Optional[str] = None,
        validate: Optional[bool] = None,
    ) -> bytes:
        """Download an in-clinic consultation voucher PDF (``getConsultationVoucher``).

        ``GET /api/consultations/{appointment_id}/voucher``. Returns the PDF bytes.
        """
        return cast(
            bytes,
            self._client._request(
                "GET",
                path("/api/consultations/{}/voucher", appointment_id),
                operation="getConsultationVoucher",
                validate=validate,
                entity_id=entity_id,
                secret_key=secret_key,
                binary=True,
            ),
        )

    def upload_documents(
        self,
        appointment_id: str,
        files: Sequence[tuple[str, FileInput]],
        *,
        entity_id: Optional[str] = None,
        secret_key: Optional[str] = None,
        validate: Optional[bool] = None,
    ) -> MessageResponse:
        """Share the member's documents with the doctor (``uploadConsultationDocuments``).

        ``POST /api/consultations/{appointment_id}/upload_documents`` (multipart). ``files``
        is a list of ``(title, file)`` pairs; each file is a path, bytes, a binary file
        object or a ``(filename, content[, content_type])`` tuple. PDF, JPEG or PNG.
        """
        parts: list[Part] = []
        for title, file in files:
            parts.append(text_part("files[][name]", title))
            parts.append(file_part("files[][value]", file))
        return cast(
            MessageResponse,
            self._client._request(
                "POST",
                path("/api/consultations/{}/upload_documents", appointment_id),
                operation="uploadConsultationDocuments",
                validate=validate,
                files=parts,
                entity_id=entity_id,
                secret_key=secret_key,
            ),
        )


class Pharmacy(_Resource):
    """ePharmacy: medicine search, prescription digitization, cart, pricing and orders."""

    def search_medicines(
        self,
        *,
        name: str,
        page: Optional[int] = None,
        entity_id: Optional[str] = None,
        secret_key: Optional[str] = None,
        validate: Optional[bool] = None,
    ) -> MedicineSearchResponse:
        """Search medicines by name, at least 3 characters (``searchMedicines``).

        ``GET /api/epharmacy/medicines/search``.
        """
        return cast(
            MedicineSearchResponse,
            self._client._request(
                "GET",
                "/api/epharmacy/medicines/search",
                operation="searchMedicines",
                validate=validate,
                params=query({"name": name, "page": page}),
                entity_id=entity_id,
                secret_key=secret_key,
            ),
        )

    def digitize_prescription(
        self,
        *,
        customer: DigitizationCustomer,
        files: Sequence[FileInput],
        plan_id: Optional[str] = None,
        idempotency_key: Optional[str] = None,
        entity_id: Optional[str] = None,
        secret_key: Optional[str] = None,
        validate: Optional[bool] = None,
    ) -> DigitizationAccepted:
        """Upload a prescription for digitization (``digitizePrescription``).

        ``POST /api/prescriptions/digitize`` (multipart). The API accepts exactly one
        customer, sent as ``customers[]``. ``files`` are JPEG, PNG or PDF (each up to 10 MB):
        paths, bytes, binary file objects or ``(filename, content[, content_type])`` tuples.
        Pass ``idempotency_key`` to make retries safe. Returns ``202`` with a ``request_id``.
        """
        # A missing field is left out of the form, so validation can report it.
        fields: Mapping[str, object] = customer
        parts = [
            text_part(f"customers[][{key}]", str(fields[key]))
            for key in ("name", "api_customer_id", "mobile_number", "gender", "dob")
            if fields.get(key) is not None
        ]
        if plan_id is not None:
            parts.append(text_part("plan_id", plan_id))
        parts.extend(file_parts("files[]", files))
        headers = {"Idempotency-Key": idempotency_key} if idempotency_key else None
        return cast(
            DigitizationAccepted,
            self._client._request(
                "POST",
                "/api/prescriptions/digitize",
                operation="digitizePrescription",
                validate=validate,
                files=parts,
                headers=headers,
                entity_id=entity_id,
                secret_key=secret_key,
            ),
        )

    def get_prescription_digitization(
        self,
        request_id: str,
        *,
        entity_id: Optional[str] = None,
        secret_key: Optional[str] = None,
        validate: Optional[bool] = None,
    ) -> DigitizationStatus:
        """Get a digitization request's status (``getPrescriptionDigitization``).

        ``GET /api/prescriptions/digitize/{request_id}``.
        """
        return cast(
            DigitizationStatus,
            self._client._request(
                "GET",
                path("/api/prescriptions/digitize/{}", request_id),
                operation="getPrescriptionDigitization",
                validate=validate,
                entity_id=entity_id,
                secret_key=secret_key,
            ),
        )

    def get_cart(
        self,
        *,
        api_customer_id: str,
        plan_id: Optional[str] = None,
        entity_id: Optional[str] = None,
        secret_key: Optional[str] = None,
        validate: Optional[bool] = None,
    ) -> CartResponse:
        """Get the member's cart (``getCart``).

        ``GET /api/epharmacy/cart`` (``api_customer_id`` is sent as
        ``customer_details[api_customer_id]``).
        """
        return cast(
            CartResponse,
            self._client._request(
                "GET",
                "/api/epharmacy/cart",
                operation="getCart",
                validate=validate,
                params=query(
                    {"customer_details[api_customer_id]": api_customer_id, "plan_id": plan_id}
                ),
                entity_id=entity_id,
                secret_key=secret_key,
            ),
        )

    def update_cart(
        self,
        *,
        customer_details: CartCustomerDetails,
        plan_id: Optional[str] = None,
        products: Optional[Sequence[CartProductInput]] = None,
        address: Optional[PharmacyAddress] = None,
        address_id: Optional[int] = None,
        fulfillment_type: Optional[Literal["delivery", "store_pickup"]] = None,
        selected_chemist_id: Optional[str] = None,
        medicine_vendor_id: Optional[int] = None,
        prescription_urls: Optional[Sequence[str]] = None,
        remove_prescription_ids: Optional[Sequence[int]] = None,
        prescription_files: Optional[Sequence[FileInput]] = None,
        entity_id: Optional[str] = None,
        secret_key: Optional[str] = None,
        validate: Optional[bool] = None,
    ) -> CartResponse:
        """Create or update the member's cart (``updateCart``).

        ``PATCH /api/epharmacy/cart``. Send at least one change. ``products`` lines with
        ``quantity: 0`` are removed.

        With ``prescription_files`` the request is sent as multipart, which (per the API
        spec) carries only ``customer_details.api_customer_id``, ``plan_id`` and the files:
        make other changes in a separate call.
        """
        if prescription_files is not None:
            others = {
                "products": products,
                "address": address,
                "address_id": address_id,
                "fulfillment_type": fulfillment_type,
                "selected_chemist_id": selected_chemist_id,
                "medicine_vendor_id": medicine_vendor_id,
                "prescription_urls": prescription_urls,
                "remove_prescription_ids": remove_prescription_ids,
            }
            extra = sorted(k for k, v in others.items() if v is not None)
            extra += sorted(k for k in customer_details if k != "api_customer_id")
            if extra:
                raise ValueError(
                    "prescription_files can only be combined with plan_id and "
                    f"customer_details.api_customer_id; got {', '.join(extra)}"
                )
            parts = [
                text_part("customer_details[api_customer_id]", customer_details["api_customer_id"])
            ]
            if plan_id is not None:
                parts.append(text_part("plan_id", plan_id))
            parts.extend(file_parts("prescription_files[]", prescription_files))
            return cast(
                CartResponse,
                self._client._request(
                    "PATCH",
                    "/api/epharmacy/cart",
                    operation="updateCart",
                    validate=validate,
                    files=parts,
                    entity_id=entity_id,
                    secret_key=secret_key,
                ),
            )
        return cast(
            CartResponse,
            self._client._request(
                "PATCH",
                "/api/epharmacy/cart",
                operation="updateCart",
                validate=validate,
                json=compact(
                    {
                        "plan_id": plan_id,
                        "customer_details": customer_details,
                        "products": _list(products),
                        "address": address,
                        "address_id": address_id,
                        "fulfillment_type": fulfillment_type,
                        "selected_chemist_id": selected_chemist_id,
                        "medicine_vendor_id": medicine_vendor_id,
                        "prescription_urls": _list(prescription_urls),
                        "remove_prescription_ids": _list(remove_prescription_ids),
                    }
                ),
                entity_id=entity_id,
                secret_key=secret_key,
            ),
        )

    def get_fulfillment_options(
        self,
        *,
        api_customer_id: str,
        cart_id: int,
        plan_id: Optional[str] = None,
        entity_id: Optional[str] = None,
        secret_key: Optional[str] = None,
        validate: Optional[bool] = None,
    ) -> FulfillmentOptions:
        """Get live delivery and store-pickup options for a cart (``getFulfillmentOptions``).

        ``GET /api/epharmacy/fulfillment_options``. Slow (typically 3-8 s). Check the nested
        ``success`` flags, not just the HTTP status.
        """
        return cast(
            FulfillmentOptions,
            self._client._request(
                "GET",
                "/api/epharmacy/fulfillment_options",
                operation="getFulfillmentOptions",
                validate=validate,
                params=query(
                    {
                        "customer_details[api_customer_id]": api_customer_id,
                        "cart_id": cart_id,
                        "plan_id": plan_id,
                    }
                ),
                entity_id=entity_id,
                secret_key=secret_key,
            ),
        )

    def get_order_payment_details(
        self,
        *,
        api_customer_id: str,
        cart_id: int,
        selected_delivery_option: DeliveryOption,
        plan_id: Optional[str] = None,
        selected_chemist_id: Optional[str] = None,
        medicine_vendor_id: Optional[int] = None,
        customer_plan_id: Optional[int] = None,
        subscription_id: Optional[str] = None,
        entity_id: Optional[str] = None,
        secret_key: Optional[str] = None,
        validate: Optional[bool] = None,
    ) -> OrderPaymentDetails:
        """Price the cart for a chosen fulfillment option (``getOrderPaymentDetails``).

        ``POST /api/epharmacy/orders/payment_details``. ``api_customer_id`` is sent as
        ``customer_details.api_customer_id``.
        """
        return cast(
            OrderPaymentDetails,
            self._client._request(
                "POST",
                "/api/epharmacy/orders/payment_details",
                operation="getOrderPaymentDetails",
                validate=validate,
                json=compact(
                    {
                        "plan_id": plan_id,
                        "customer_details": {"api_customer_id": api_customer_id},
                        "cart_id": cart_id,
                        "selected_delivery_option": selected_delivery_option,
                        "selected_chemist_id": selected_chemist_id,
                        "medicine_vendor_id": medicine_vendor_id,
                        "customer_plan_id": customer_plan_id,
                        "subscription_id": subscription_id,
                    }
                ),
                entity_id=entity_id,
                secret_key=secret_key,
            ),
        )

    def create_order(
        self,
        *,
        api_customer_id: str,
        cart_id: int,
        plan_id: Optional[str] = None,
        delivery_option: Optional[DeliveryOption] = None,
        delivery_type: Optional[Literal["delivery", "pickup"]] = None,
        location_token: Optional[str] = None,
        medicine_vendor_id: Optional[int] = None,
        coupon_code: Optional[str] = None,
        customer_plan_id: Optional[int] = None,
        subscription_id: Optional[str] = None,
        entity_id: Optional[str] = None,
        secret_key: Optional[str] = None,
        validate: Optional[bool] = None,
    ) -> CreateOrderResponse:
        """Place an order from the cart (``createOrder``).

        ``POST /api/epharmacy/orders``. Pass the chosen option's ``location_token`` from
        ``get_fulfillment_options``. ``api_customer_id`` is sent as
        ``customer_details.api_customer_id``.
        """
        return cast(
            CreateOrderResponse,
            self._client._request(
                "POST",
                "/api/epharmacy/orders",
                operation="createOrder",
                validate=validate,
                json=compact(
                    {
                        "plan_id": plan_id,
                        "customer_details": {"api_customer_id": api_customer_id},
                        "cart_id": cart_id,
                        "delivery_option": delivery_option,
                        "delivery_type": delivery_type,
                        "location_token": location_token,
                        "medicine_vendor_id": medicine_vendor_id,
                        "coupon_code": coupon_code,
                        "customer_plan_id": customer_plan_id,
                        "subscription_id": subscription_id,
                    }
                ),
                entity_id=entity_id,
                secret_key=secret_key,
            ),
        )

    def list_orders(
        self,
        *,
        api_customer_id: str,
        page: Optional[int] = None,
        per_page: Optional[int] = None,
        entity_id: Optional[str] = None,
        secret_key: Optional[str] = None,
        validate: Optional[bool] = None,
    ) -> OrderList:
        """List a member's orders (``listOrders``).

        ``GET /api/epharmacy/orders``.
        """
        return cast(
            OrderList,
            self._client._request(
                "GET",
                "/api/epharmacy/orders",
                operation="listOrders",
                validate=validate,
                params=query(
                    {
                        "customer_details[api_customer_id]": api_customer_id,
                        "page": page,
                        "per_page": per_page,
                    }
                ),
                entity_id=entity_id,
                secret_key=secret_key,
            ),
        )

    def get_order(
        self,
        order_id: str,
        *,
        api_customer_id: str,
        entity_id: Optional[str] = None,
        secret_key: Optional[str] = None,
        validate: Optional[bool] = None,
    ) -> OrderResponse:
        """Get an order (``getOrder``).

        ``GET /api/epharmacy/orders/{order_id}``.
        """
        return cast(
            OrderResponse,
            self._client._request(
                "GET",
                path("/api/epharmacy/orders/{}", order_id),
                operation="getOrder",
                validate=validate,
                params=query({"customer_details[api_customer_id]": api_customer_id}),
                entity_id=entity_id,
                secret_key=secret_key,
            ),
        )

    def cancel_order(
        self,
        order_id: str,
        *,
        api_customer_id: str,
        plan_id: Optional[str] = None,
        reason: Optional[str] = None,
        message: Optional[str] = None,
        entity_id: Optional[str] = None,
        secret_key: Optional[str] = None,
        validate: Optional[bool] = None,
    ) -> CancelOrderResponse:
        """Cancel an order (``cancelOrder``).

        ``PATCH /api/epharmacy/orders/{order_id}/cancel``.
        """
        return cast(
            CancelOrderResponse,
            self._client._request(
                "PATCH",
                path("/api/epharmacy/orders/{}/cancel", order_id),
                operation="cancelOrder",
                validate=validate,
                json=compact(
                    {
                        "plan_id": plan_id,
                        "customer_details": {"api_customer_id": api_customer_id},
                        "reason": reason,
                        "message": message,
                    }
                ),
                entity_id=entity_id,
                secret_key=secret_key,
            ),
        )

    def confirm_order(
        self,
        order_id: str,
        *,
        api_customer_id: str,
        partner_collected_amount: str,
        partner_payment_reference: str,
        entity_id: Optional[str] = None,
        secret_key: Optional[str] = None,
        validate: Optional[bool] = None,
    ) -> ConfirmOrderResponse:
        """Confirm a partner-collected payment (``confirmOrder``).

        ``POST /api/epharmacy/orders/{order_id}/confirm``. ``partner_collected_amount`` is a
        decimal string (for example ``"1200.00"``). Safe to retry; ``409`` means a concurrent
        confirmation is in progress.
        """
        return cast(
            ConfirmOrderResponse,
            self._client._request(
                "POST",
                path("/api/epharmacy/orders/{}/confirm", order_id),
                operation="confirmOrder",
                validate=validate,
                json={
                    "customer_details": {"api_customer_id": api_customer_id},
                    "partner_collected_amount": partner_collected_amount,
                    "partner_payment_reference": partner_payment_reference,
                },
                entity_id=entity_id,
                secret_key=secret_key,
            ),
        )


class Wallet(_Resource):
    """Member benefit wallets and plan subscriptions."""

    def get_customer_wallet(
        self,
        company_slug: str,
        *,
        api_customer_id: Optional[str] = None,
        customer_id: Optional[str] = None,
        plan_id: Optional[str] = None,
        customer_plan_id: Optional[int] = None,
        subscription_id: Optional[str] = None,
        entity_id: Optional[str] = None,
        secret_key: Optional[str] = None,
        validate: Optional[bool] = None,
    ) -> WalletResponse:
        """Get a member's (and their family's) benefit balances (``getCustomerWallet``).

        ``GET /api/{company_slug}/customers/wallet``. Send ``api_customer_id`` or
        ``customer_id``.
        """
        return cast(
            WalletResponse,
            self._client._request(
                "GET",
                path("/api/{}/customers/wallet", company_slug),
                operation="getCustomerWallet",
                validate=validate,
                params=query(
                    {
                        "plan_id": plan_id,
                        "api_customer_id": api_customer_id,
                        "customer_id": customer_id,
                        "customer_plan_id": customer_plan_id,
                        "subscription_id": subscription_id,
                    }
                ),
                entity_id=entity_id,
                secret_key=secret_key,
            ),
        )

    def list_customer_plans(
        self,
        company_slug: str,
        *,
        api_customer_id: Optional[str] = None,
        customer_id: Optional[str] = None,
        entity_id: Optional[str] = None,
        secret_key: Optional[str] = None,
        validate: Optional[bool] = None,
    ) -> CustomerPlansResponse:
        """List a member's plan subscriptions (``listCustomerPlans``).

        ``GET /api/{company_slug}/customers/plans``. Send ``api_customer_id`` or
        ``customer_id``.
        """
        return cast(
            CustomerPlansResponse,
            self._client._request(
                "GET",
                path("/api/{}/customers/plans", company_slug),
                operation="listCustomerPlans",
                validate=validate,
                params=query({"api_customer_id": api_customer_id, "customer_id": customer_id}),
                entity_id=entity_id,
                secret_key=secret_key,
            ),
        )


class PreRegistration(_Resource):
    """Register, update and deactivate members and their dependants in bulk.

    Uses the pre-registration credentials (``pre_registration_username`` /
    ``pre_registration_password``); their token is sent as ``X-EKINCARE-KEY``. Writes are
    processed asynchronously: each returns a ``request_id`` to poll with ``get_status``.
    At most 250 rows per call.
    """

    def get_access_token(self) -> PreRegistrationAccessToken:
        """Fetch a new pre-registration token (``getPreRegistrationAccessToken``) and cache it.

        ``GET /api/pre_registration/access-token``. You don't need to call this: the client
        fetches and refreshes the token on its own.
        """
        token = self._client._new_token(pre_registration=True)
        return cast(PreRegistrationAccessToken, token)

    def create(
        self,
        *,
        employees: Optional[Sequence[PreRegistrationEmployee]] = None,
        dependants: Optional[Sequence[PreRegistrationDependant]] = None,
        validate: Optional[bool] = None,
    ) -> PreRegistrationAccepted:
        """Pre-register members and dependants (``createPreRegistrations``).

        ``POST /v1/corporate/pre_registrations``. Every required key must be present in each
        row, even when empty: the API silently drops rows that miss one.
        """
        return cast(
            PreRegistrationAccepted,
            self._client._request(
                "POST",
                "/v1/corporate/pre_registrations",
                operation="createPreRegistrations",
                validate=validate,
                json=compact({"employees": _list(employees), "dependants": _list(dependants)}),
                pre_registration=True,
            ),
        )

    def update(
        self,
        *,
        employees: Optional[Sequence[PreRegistrationEmployeeUpdate]] = None,
        dependants: Optional[Sequence[PreRegistrationDependantUpdate]] = None,
        validate: Optional[bool] = None,
    ) -> PreRegistrationAccepted:
        """Update registered members and dependants (``updatePreRegistrations``).

        ``POST /v1/corporate/pre_registrations/update``. Send each row's identifier and only
        the fields to change.
        """
        return cast(
            PreRegistrationAccepted,
            self._client._request(
                "POST",
                "/v1/corporate/pre_registrations/update",
                operation="updatePreRegistrations",
                validate=validate,
                json=compact({"employees": _list(employees), "dependants": _list(dependants)}),
                pre_registration=True,
            ),
        )

    def deactivate(
        self,
        *,
        employees: Optional[Sequence[str]] = None,
        dependants: Optional[Sequence[str]] = None,
        validate: Optional[bool] = None,
    ) -> PreRegistrationAccepted:
        """Deactivate members or dependants (``deactivatePreRegistrations``).

        ``POST /v1/corporate/pre_registrations/deactivate``. ``employees`` are emails,
        ``dependants`` are mobile numbers. Deactivating an employee deactivates their
        dependants too.
        """
        return cast(
            PreRegistrationAccepted,
            self._client._request(
                "POST",
                "/v1/corporate/pre_registrations/deactivate",
                operation="deactivatePreRegistrations",
                validate=validate,
                json=compact({"employees": _list(employees), "dependants": _list(dependants)}),
                pre_registration=True,
            ),
        )

    def get_status(
        self, request_id: str, *, validate: Optional[bool] = None
    ) -> PreRegistrationStatus:
        """Get the outcome of a create, update or deactivate call (``getPreRegistrationStatus``).

        ``GET /v1/corporate/pre_registrations/{request_id}/status``. Poll until ``status`` is
        ``completed``.
        """
        return cast(
            PreRegistrationStatus,
            self._client._request(
                "GET",
                path("/v1/corporate/pre_registrations/{}/status", request_id),
                operation="getPreRegistrationStatus",
                validate=validate,
                pre_registration=True,
            ),
        )


class Testing(_Resource):
    """**Staging only.** Move bookings and orders through their lifecycle.

    These endpoints exist only on ``https://staging-api.hlthstack.io``; production returns
    401 or 404. Each call fires the same webhooks a real status change would.
    """

    def simulate_appointment_status(
        self,
        appointment_id: str,
        *,
        status: AppointmentSimulationStatus,
        entity_id: Optional[str] = None,
        secret_key: Optional[str] = None,
        validate: Optional[bool] = None,
    ) -> MessagesResponse:
        """(Staging only) Move a health-checkup appointment (``simulateAppointmentStatus``).

        ``POST /api/appointments/{appointment_id}/update_status``.
        """
        return cast(
            MessagesResponse,
            self._client._request(
                "POST",
                path("/api/appointments/{}/update_status", appointment_id),
                operation="simulateAppointmentStatus",
                validate=validate,
                json={"status": status},
                entity_id=entity_id,
                secret_key=secret_key,
            ),
        )

    def simulate_consultation_status(
        self,
        appointment_id: str,
        *,
        status: ConsultationSimulationStatus,
        reschedule_time: Optional[DateTime] = None,
        entity_id: Optional[str] = None,
        secret_key: Optional[str] = None,
        validate: Optional[bool] = None,
    ) -> MessagesResponse:
        """(Staging only) Move a consultation (``simulateConsultationStatus``).

        ``PATCH /api/consultations/{appointment_id}/update_status``.
        """
        return cast(
            MessagesResponse,
            self._client._request(
                "PATCH",
                path("/api/consultations/{}/update_status", appointment_id),
                operation="simulateConsultationStatus",
                validate=validate,
                json=compact({"status": status, "reschedule_time": datetime_utc(reschedule_time)}),
                entity_id=entity_id,
                secret_key=secret_key,
            ),
        )

    def simulate_order_status(
        self,
        order_id: str,
        *,
        api_customer_id: str,
        status: str,
        status_text: Optional[str] = None,
        status_description: Optional[str] = None,
        tracking_number: Optional[str] = None,
        tracking_url: Optional[str] = None,
        tracking_partner: Optional[str] = None,
        entity_id: Optional[str] = None,
        secret_key: Optional[str] = None,
        validate: Optional[bool] = None,
    ) -> SimulateOrderStatusResponse:
        """(Staging only) Move a pharmacy order to an order status (``simulateOrderStatus``).

        ``PATCH /api/epharmacy/orders/{order_id}/update_status``.
        """
        return cast(
            SimulateOrderStatusResponse,
            self._client._request(
                "PATCH",
                path("/api/epharmacy/orders/{}/update_status", order_id),
                operation="simulateOrderStatus",
                validate=validate,
                json=compact(
                    {
                        "customer_details": {"api_customer_id": api_customer_id},
                        "status": status,
                        "status_text": status_text,
                        "status_description": status_description,
                        "tracking_number": tracking_number,
                        "tracking_url": tracking_url,
                        "tracking_partner": tracking_partner,
                    }
                ),
                entity_id=entity_id,
                secret_key=secret_key,
            ),
        )


def _list(value: Optional[Sequence[object]]) -> Optional[list[object]]:
    return None if value is None else list(value)
