"""Typed shapes of hlthstack request and response bodies.

These are ``TypedDict`` definitions that mirror the schemas in the hlthstack OpenAPI spec
(https://github.com/hlthstack/integration-guide/blob/main/openapi/openapi.yaml). They are
type hints only: at runtime every response is a plain ``dict`` parsed from JSON.

Response types are declared with ``total=False`` because the API omits many keys depending
on state (see the guides). Use ``.get()`` for keys that are not always present.
"""

from typing import Any, Literal, Optional, TypedDict, Union

Gender = Literal["male", "female", "non-binary"]
AppointmentType = Literal["home_collection", "inclinic"]
DeliveryOption = Literal["express", "standard", "store_pickup"]
AppointmentSimulationStatus = Literal[
    "confirm",
    "assign_phlebo",
    "cancel",
    "completed",
    "reschedule",
    "reports_partially_received",
    "reports_received",
    "lab_result",
]
ConsultationSimulationStatus = Literal[
    "confirm", "cancel", "completed", "reschedule", "reports_received"
]

# --------------------------------------------------------------------------- shared


class AccessToken(TypedDict):
    access_token: str
    expires_at: str


class MessageResponse(TypedDict):
    message: str


class MessagesResponse(TypedDict):
    messages: list[str]


class PartialResult(TypedDict, total=False):
    """Booking-level reschedule/cancel result. ``success``/``failed`` are comma-separated ids."""

    message: str
    success: str
    failed: str


class FileLink(TypedDict, total=False):
    file_name: Optional[str]
    file_url: Optional[str]


# --------------------------------------------------------------------------- providers & slots


class Provider(TypedDict, total=False):
    provider_id: int
    provider_name: Optional[str]
    locality: Optional[str]
    city: Optional[str]
    state: Optional[str]
    pincode: Optional[str]
    address: Optional[str]
    latitude: Optional[float]
    longitude: Optional[float]
    timezone: str
    timezone_info: Optional[str]
    home_collection_enabled: Optional[bool]
    serviceable: Optional[bool]
    is_center_available: Optional[bool]
    estimated_time: Optional[str]
    estimated_distance: Optional[str]
    distance: Optional[float]
    rating: Optional[float]
    slot_lead_time: Optional[int]
    opening_time: Optional[str]
    closing_time: Optional[str]
    selling_price: Union[float, str, None]
    total_mrp: Union[float, str, None]
    report_turn_around_time: Any
    disrupted_dates: Any
    provider_slots: Optional[dict[str, Any]]
    doctor_id: str
    doctor_name: str
    doctor_specialities: list[str]
    doctor_experience: Optional[int]
    doctor_qualification: Optional[str]
    doctor_languages: list[str]
    doctor_fee_details: dict[str, Union[str, float]]
    doctor_availability: Optional[str]
    doctor_photo: dict[str, Optional[str]]
    doctor_gender: Optional[str]
    hospital_name: Optional[str]
    hospital_location: Optional[str]
    next_available_slot: Any
    visited_before: Optional[bool]


class ProvidersResponse(TypedDict, total=False):
    providers: list[Provider]
    total_results: int
    page: int
    min_price: Optional[float]
    fasting_required: Optional[bool]
    fasting_alert: Optional[str]
    payment_type: Optional[str]
    additional_info: Optional[dict[str, Any]]
    home_collection_available: Optional[bool]
    home_collection_provider: Optional[dict[str, Any]]
    auto_allocate_provider: Optional[bool]


class Slot(TypedDict, total=False):
    start_time: str
    end_time: str
    slot: str
    available: bool
    display_text: str
    slot_text: str
    utc_slot_time: str
    start_time_in_timezone: str
    end_time_in_timezone: str
    remaining_capacity: Optional[int]
    partner_slot_id: Any
    vendor_refs: dict[str, Any]


class SlotDay(TypedDict, total=False):
    date: str
    slots: list[Slot]


class SlotsResponse(TypedDict, total=False):
    booking_slots: list[SlotDay]
    date: str
    """Deprecated: first day only. Read ``booking_slots``."""
    slots: list[Slot]
    """Deprecated: first day only. Read ``booking_slots``."""
    report_tat: Any
    interval: Optional[int]
    unavailable_reason: Optional[str]


# --------------------------------------------------------------------------- appointments


class BookingAddress(TypedDict):
    address_line_one: str
    address_line_two: str
    city: str
    state: str
    country: str
    pincode: str
    latitude: float
    longitude: float


class _BookingCustomerRequired(TypedDict):
    name: str
    api_customer_id: str
    mobile_number: str
    gender: Gender
    dob: str
    package_ids: list[Union[int, str]]


class BookingCustomer(_BookingCustomerRequired, total=False):
    booking_customer: bool
    vip: bool
    api_partner_order_id: str
    service_type: str


class BookedCustomer(TypedDict, total=False):
    customer_id: int
    name: str
    api_customer_id: str
    package_ids: list[Union[int, str]]
    appointment_id: str
    customer_plan_id: Optional[int]
    subscription_id: Optional[str]


class CreateAppointmentResponse(TypedDict, total=False):
    provider_id: Union[int, str]
    home_collection_enable: bool
    booking_id: str
    status: Literal["confirmed", "payment_pending"]
    payment_link: str
    payment_link_expires_at: str
    customers: list[BookedCustomer]


class _PaymentDetailsCustomerRequired(TypedDict):
    api_customer_id: str
    package_ids: list[int]


class PaymentDetailsCustomer(_PaymentDetailsCustomerRequired, total=False):
    booking_customer: bool


class AppointmentPaymentBreakdown(TypedDict, total=False):
    total_amount: float
    sponsor_wallet_amount: float
    customer_wallet_amount: float
    promotional_wallet_amount: float
    razorpay_amount: float
    currency: str


class AppointmentPaymentDetailsResponse(TypedDict, total=False):
    payment_details: AppointmentPaymentBreakdown


class AppointmentPayment(TypedDict, total=False):
    status: str
    total_collected_amount: Union[str, float]
    razorpay_amount: Union[str, float]
    razorpay_payment_id: Optional[str]
    razorpay_order_id: Optional[str]
    customer_wallet_amount: Union[str, float]
    sponsor_wallet_amount: Union[str, float]
    promotional_wallet_amount: Union[str, float]
    cod_amount: Union[str, float]
    h_points_amount: Union[str, float]
    refunded_amount: Union[str, float]
    captured_at: Optional[str]
    refunded_at: Optional[str]


class AppointmentDetails(TypedDict, total=False):
    """One appointment or consultation. Same shape as the status-update webhook body."""

    type: Literal["status_update", "reports_upload"]
    booking_id: str
    appointment_id: str
    customer_id: str
    customer_name: str
    mobile_number: Optional[str]
    api_customer_id: Optional[str]
    member_id: Optional[str]
    appointment_date_time: str
    event_timestamp: float
    booking_source: Optional[str]
    service_type: str
    plan_id: Optional[str]
    customer_plan_id: Optional[int]
    subscription_id: Optional[str]
    status: str
    status_text: str
    comment: Optional[str]
    provider_id: int
    provider_name: Optional[str]
    provider_branch: Optional[str]
    provider_address: Optional[str]
    voucher_api_url: str
    phlebo_name: str
    phlebo_number: str
    reports: list[str]
    doctor_id: str
    doctor_name: str
    doctor_specialities: list[str]
    doctor_gender: Optional[str]
    doctor_qualification: Optional[str]
    doctor_languages: list[str]
    doctor_experience: Optional[int]
    summary: FileLink
    doctor_prescriptions: list[FileLink]
    latitude: Union[float, str, None]
    longitude: Union[float, str, None]
    hospital_name: Optional[str]
    hospital_location: Optional[str]
    hospital_address: Optional[str]
    meeting_link: Optional[str]
    payment: AppointmentPayment


class BookingDetails(TypedDict, total=False):
    booking_id: str
    service_name: str
    appointments: list[AppointmentDetails]


class CustomerAppointmentsResponse(TypedDict):
    appointments: list[AppointmentDetails]


class AppointmentReportsResponse(TypedDict, total=False):
    """``reports`` when reports exist, otherwise ``message``."""

    reports: list[str]
    message: str


class LabResult(TypedDict, total=False):
    result: Optional[str]
    units: Optional[str]
    ranges: Optional[str]
    test_component_id: int
    test_component_name: str
    lab_test_id: int
    lab_test_name: str


class LabResultNote(TypedDict, total=False):
    title: str
    description: str


class LabResultsDigitization(TypedDict, total=False):
    results: list[LabResult]
    notes: list[LabResultNote]


class LabResults(TypedDict, total=False):
    type: Literal["lab_results"]
    booking_id: str
    appointment_id: str
    customer_id: str
    api_customer_id: Optional[str]
    member_id: Optional[str]
    plan_id: Optional[str]
    digitization: LabResultsDigitization


# --------------------------------------------------------------------------- consultations


class ConsultationCustomer(TypedDict):
    name: str
    api_customer_id: str
    mobile_number: str
    gender: Gender
    dob: str
    package_ids: list[Union[int, str]]


class BookedConsultationCustomer(TypedDict, total=False):
    customer_id: str
    name: str
    api_customer_id: str
    package_ids: list[Union[int, str]]
    appointment_id: str
    consultation_status: str
    customer_plan_id: Optional[int]
    subscription_id: Optional[str]


class CreateConsultationResponse(TypedDict, total=False):
    provider_id: Union[int, str]
    booking_id: str
    status: Literal["confirmed"]
    payment_link: str
    payment_link_expires_at: str
    customers: list[BookedConsultationCustomer]


class ConsultationDetails(TypedDict, total=False):
    booking_id: str
    appointment_id: str
    appointment_date_time: str
    status: str
    service_name: str
    service_mode: str
    api_customer_id: Optional[str]
    customer_id: str
    doctor_id: Optional[str]
    doctor_name: Optional[str]
    doctor_specialities: Optional[list[str]]
    doctor_gender: Optional[str]
    doctor_qualification: Optional[str]
    doctor_languages: Optional[list[str]]
    doctor_experience: int
    provider_id: int
    is_priority_consultation: bool
    is_default_provider: bool
    latitude: Union[float, str, None]
    longitude: Union[float, str, None]
    hospital_name: Optional[str]
    hospital_location: Optional[str]
    hospital_address: Optional[str]
    summary: FileLink
    prescriptions: list[FileLink]
    meeting_link: Optional[str]


class ConsultationCancelResponse(TypedDict):
    msg: str


class SummaryAndPrescription(TypedDict, total=False):
    summary: FileLink
    doctor_prescriptions: list[FileLink]


# --------------------------------------------------------------------------- ePharmacy


class Medicine(TypedDict, total=False):
    id: int
    name: str
    composition_with_strength: Optional[str]
    manufacturer_name: Optional[str]
    packing_label: Optional[str]
    mrp: Optional[float]
    available: bool
    type: Optional[str]
    rx_required: bool


class MedicineSearchResponse(TypedDict, total=False):
    medicines: list[Medicine]
    meta: dict[str, int]


class DigitizationCustomer(TypedDict):
    name: str
    api_customer_id: str
    mobile_number: str
    gender: Gender
    dob: str


class DigitizationAccepted(TypedDict, total=False):
    request_id: str
    digitization_id: str
    status: str
    message: str


class DigitizationStatus(TypedDict, total=False):
    request_id: str
    status: Literal[
        "pending", "ai_processing", "manual_review", "completed", "partial", "rejected", "failed"
    ]
    api_customer_id: str
    files: list[dict[str, str]]
    message: str
    items: list[dict[str, Any]]
    cart_id: Optional[int]
    error: Optional[str]


class CartProduct(TypedDict, total=False):
    id: int
    name: str
    type: Optional[str]
    quantity: int
    mrp: Union[str, float]
    discount_price: Optional[float]
    discount_percent: Optional[str]
    rx_required: bool
    is_available: bool
    is_banned: bool
    pack_size_label: Optional[str]
    limit_per_order: Optional[int]
    min_limit_per_order: Optional[int]
    image: Optional[str]


class CartPrescription(TypedDict, total=False):
    id: int
    url: str
    name: str
    status: str


class Cart(TypedDict, total=False):
    id: int
    api_customer_id: str
    plan_id: Optional[str]
    products: list[CartProduct]
    prescription_ids: list[int]
    prescriptions: list[CartPrescription]
    address_id: Optional[int]
    city: Optional[str]
    zip_code: Optional[str]
    coupon_code: Optional[str]
    doctor_call_required: Optional[bool]
    fulfillment_type: Optional[Literal["delivery", "store_pickup"]]
    selected_store_data: dict[str, Any]
    eta: Any


class CartResponse(TypedDict):
    success: bool
    cart: Cart


class _CartCustomerDetailsRequired(TypedDict):
    api_customer_id: str


class CartCustomerDetails(_CartCustomerDetailsRequired, total=False):
    """``api_customer_id`` plus optional details that create or enrich the member."""

    name: str
    dob: str
    mobile_number: str
    gender: str


class CartProductInput(TypedDict):
    id: int
    quantity: int


class _PharmacyAddressRequired(TypedDict):
    line1: str
    city: str
    state: str
    pincode: str


class PharmacyAddress(_PharmacyAddressRequired, total=False):
    line2: str
    country: str
    land_mark: str
    latitude: float
    longitude: float


class FulfillmentOption(TypedDict, total=False):
    vendor_id: int
    mrp: float
    selling_price: float
    additional_charges: float
    express_premium: float
    total_payable: float
    discount_price: float
    delivery_details: dict[str, Any]
    products: list[dict[str, Any]]
    missing_products: list[dict[str, Any]]
    location_token: str


class DeliveryOptions(TypedDict, total=False):
    success: bool
    location_not_servicable: bool
    message: str
    express: FulfillmentOption
    standard: FulfillmentOption


class PickupStore(TypedDict, total=False):
    id: str
    name: str
    address: str
    latitude: Union[str, float]
    longitude: Union[str, float]
    display_eta: str
    distance: float
    location_token: str


class PickupVendor(TypedDict, total=False):
    success: bool
    vendor_id: int
    stores: list[PickupStore]


class PickupOptions(TypedDict, total=False):
    success: bool
    starting_from: float
    vendors: list[PickupVendor]


class FulfillmentOptions(TypedDict, total=False):
    """Check the nested ``success`` flags: HTTP 200 can still carry ``success: false``."""

    success: bool
    delivery_options: DeliveryOptions
    pickup_options: PickupOptions


class OrderPaymentBreakdown(TypedDict, total=False):
    total_mrp: float
    sub_total: float
    discount: float
    shipping_charge: float
    free_shipping: bool
    total_amount: float
    wallet_deduction: float
    spending_balance_deduction: float
    total_payable: float
    partner_payment_required: bool
    amount_to_collect: float


class OrderPaymentDetails(TypedDict, total=False):
    products: list[dict[str, Any]]
    payment_details: OrderPaymentBreakdown
    estimated_time: Optional[str]
    fulfillment: dict[str, Any]
    address: dict[str, Any]


class OrderItem(TypedDict, total=False):
    id: Union[int, str]
    product_id: Optional[str]
    name: str
    quantity: int
    mrp: float
    offered_price: float
    selling_price: float
    discounted_price: float


class SplitDetails(TypedDict, total=False):
    is_splitted: bool
    parent_order: Any
    sub_orders: list[dict[str, Any]]


class Order(TypedDict, total=False):
    unique_id: str
    status: str
    status_text: Optional[str]
    status_description: Optional[str]
    partner_status: Optional[str]
    created_at: str
    otp: Optional[str]
    vendor_name: Optional[str]
    order_type: Optional[str]
    api_customer_id: Optional[str]
    tracking_number: Optional[str]
    tracking_url: Optional[str]
    tracking_partner: Optional[str]
    eta_from: Optional[str]
    eta_to: Optional[str]
    invoice_url: Optional[str]
    payment_details: dict[str, Any]
    products: list[OrderItem]
    address: dict[str, Any]
    prescriptions: list[str]
    split_details: SplitDetails


class CreateOrderResponse(TypedDict, total=False):
    success: bool
    status: Literal["confirmed", "payment_pending", "partner_payment_pending"]
    booking_id: int
    order_id: str
    payment_link: str
    amount_to_collect: float
    currency: str
    user_prescription_details: Order


class OrdersPage(TypedDict, total=False):
    current_page: int
    next_page: Optional[int]
    prev_page: Optional[int]
    total_pages: int
    total_count: int


class OrderList(TypedDict):
    success: bool
    orders: list[Order]
    meta: OrdersPage


class OrderResponse(TypedDict):
    success: bool
    order: Order


class CancelOrderResponse(TypedDict):
    success: bool
    order_id: str
    status: str


class _ConfirmOrderResponseRequired(TypedDict):
    success: bool
    status: Literal["confirmed", "already_confirmed"]
    order_id: str


class ConfirmOrderResponse(_ConfirmOrderResponseRequired, total=False):
    partner_collected_amount: float
    partner_payment_reference: str
    vendor_order_status: str


class SimulateOrderStatusResponse(TypedDict, total=False):
    success: bool
    order_id: str
    status: str
    journey: list[dict[str, Any]]


# --------------------------------------------------------------------------- wallet


class WalletBenefit(TypedDict, total=False):
    benefit_type: str
    allocated_benefit_amount: float
    available_benefit_amount: float
    allocated_benefit_utilization_count: int
    current_benefit_utilization_count: int


class WalletDetails(TypedDict, total=False):
    benefits: list[WalletBenefit]
    total_allocated_amount: float
    available_amount: float


class WalletMember(TypedDict, total=False):
    name: str
    gender: Optional[str]
    dob: Optional[str]
    phone: Optional[str]
    email: Optional[str]
    relationship: str
    relation: str
    member_status: Literal["ACTIVE", "INACTIVE"]
    wallet_details: WalletDetails


class WalletData(TypedDict, total=False):
    customer_plan_id: int
    subscription_id: Optional[str]
    members: list[WalletMember]


class WalletResponse(TypedDict):
    status: Literal["success"]
    data: WalletData


class CustomerPlan(TypedDict, total=False):
    customer_plan_id: int
    subscription_id: Optional[str]
    plan_id: str
    plan_name: str
    start_date: str
    end_date: Optional[str]
    grace_end_date: Optional[str]
    status: Literal["active", "upcoming", "grace"]
    available_balance: float


class CustomerPlansData(TypedDict):
    customer_plans: list[CustomerPlan]


class CustomerPlansResponse(TypedDict):
    status: Literal["success"]
    data: CustomerPlansData


# --------------------------------------------------------------------------- pre-registration


class PreRegistrationAccessToken(TypedDict):
    access_token: str
    expires_at: str
    """UTC, formatted ``2026-01-15 07:16:21 UTC`` (not ISO 8601)."""


class _VoluntaryPlanSubscriptionRequired(TypedDict):
    plan_id: str


class VoluntaryPlanSubscription(_VoluntaryPlanSubscriptionRequired, total=False):
    start_date: str
    additional: bool
    subscription_id: str


VoluntaryPlanEntry = Union[str, VoluntaryPlanSubscription]
"""A plan id, or a :class:`VoluntaryPlanSubscription` naming one subscription."""


class _PreRegistrationEmployeeRequired(TypedDict):
    # Every key here must be present, even when empty: rows missing one are dropped silently.
    company_id: Union[str, int]
    employee_code: Optional[str]
    first_name: str
    last_name: Optional[str]
    date_of_birth: Optional[str]
    gender: Optional[str]
    mobile_number: Optional[str]
    vip: Optional[str]
    entity_name: Optional[str]
    employee_office_location: Optional[str]
    department: Optional[str]
    grade: Optional[str]
    date_of_joining: Optional[str]


class PreRegistrationEmployee(_PreRegistrationEmployeeRequired, total=False):
    """A member to register. Send ``email``, or a non-empty ``employee_code``."""

    email: Optional[str]
    api_customer_id: Optional[str]
    voluntary_plan_ids: list[VoluntaryPlanEntry]


class _PreRegistrationDependantRequired(TypedDict):
    # Every key here must be present, even when empty: rows missing one are dropped silently.
    first_name: str
    last_name: Optional[str]
    date_of_birth: Optional[str]
    gender: Optional[str]
    mobile_number: Optional[str]
    relation: Optional[str]


class PreRegistrationDependant(_PreRegistrationDependantRequired, total=False):
    """A dependant, linked by ``guardian_email`` or ``company_id`` + ``guardian_employee_code``."""

    guardian_email: Optional[str]
    company_id: Union[str, int, None]
    guardian_employee_code: Optional[str]
    dependent_code: Optional[str]
    email: Optional[str]
    api_customer_id: Optional[str]
    authorised_dependent: Optional[str]


class PreRegistrationEmployeeUpdate(TypedDict, total=False):
    """Identify by ``email``, or ``company_id`` + ``employee_code``; add the fields to change."""

    email: str
    company_id: Union[str, int]
    employee_code: Optional[str]
    first_name: str
    last_name: Optional[str]
    date_of_birth: Optional[str]
    gender: Optional[str]
    mobile_number: Optional[str]
    vip: Optional[str]
    entity_name: Optional[str]
    employee_office_location: Optional[str]
    department: Optional[str]
    grade: Optional[str]
    date_of_joining: Optional[str]
    api_customer_id: Optional[str]
    voluntary_plan_ids: list[VoluntaryPlanEntry]


class PreRegistrationDependantUpdate(TypedDict, total=False):
    """Identify by ``api_customer_id`` / ``dependent_code`` (with the guardian) or mobile."""

    guardian_email: str
    company_id: Union[str, int]
    guardian_employee_code: str
    api_customer_id: str
    dependent_code: str
    mobile_number: str
    first_name: str
    last_name: Optional[str]
    email: Optional[str]
    date_of_birth: Optional[str]
    gender: Optional[str]
    relation: str
    authorised_dependent: str


class PreRegistrationAccepted(TypedDict):
    message: str
    request_id: str


class PreRegistrationCustomerPlan(TypedDict, total=False):
    customer_plan_id: int
    subscription_id: Optional[str]
    plan_id: Optional[str]
    plan_name: Optional[str]
    start_date: str
    end_date: str
    grace_end_date: str
    status: Literal["active", "upcoming", "grace"]


class PreRegistrationSuccessRecord(TypedDict, total=False):
    employee_code: Optional[str]
    first_name: Optional[str]
    last_name: Optional[str]
    email: Optional[str]
    date_of_birth: Optional[str]
    gender: Optional[str]
    mobile_number: Optional[str]
    vip: Literal["Yes", "No"]
    entity_name: Optional[str]
    employee_office_location: Optional[str]
    department: Optional[str]
    customer_token: Optional[str]
    errors: list[str]
    grade: Optional[str]
    guardian_email: Optional[str]
    relation: Optional[str]
    customer_plans: list[PreRegistrationCustomerPlan]
    status: Literal["Active", "Inactive"]


class PreRegistrationFailureRecord(TypedDict, total=False):
    """Create/update rows echo their fields; deactivate rows carry ``errors`` only."""

    employee_code: Optional[str]
    first_name: Optional[str]
    last_name: Optional[str]
    email: Optional[str]
    date_of_birth: Optional[str]
    gender: Optional[str]
    mobile_number: Optional[str]
    vip: Optional[str]
    entity_name: Optional[str]
    employee_office_location: Optional[str]
    department: Optional[str]
    guardian_email: Optional[str]
    errors: list[str]


class PreRegistrationStatus(TypedDict):
    request_id: str
    status: Literal["initialized", "scheduled", "inprogress", "completed", "failed"]
    success_records: list[PreRegistrationSuccessRecord]
    failure_records: list[PreRegistrationFailureRecord]
    created_at: str
