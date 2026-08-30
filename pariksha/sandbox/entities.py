"""Razorpay entity models, annotated with per-field data provenance.

Trusted fields are produced by Razorpay, a bank or a card network. Untrusted
fields are written by a customer, merchant or counterparty and are never an
instruction source. See D-009, D-010.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

Provenance = Literal["trusted", "untrusted"]


def trusted(description: str, **kw: Any) -> Any:
    """A field Razorpay, a bank, or a card network produced."""
    return Field(description=description, json_schema_extra={"provenance": "trusted"}, **kw)


def untrusted(description: str, **kw: Any) -> Any:
    """A field an external party wrote."""
    return Field(description=description, json_schema_extra={"provenance": "untrusted"}, **kw)


class RazorpayEntity(BaseModel):
    """Base class carrying the provenance introspection helpers."""

    @classmethod
    def untrusted_fields(cls) -> frozenset[str]:
        """Field names on this entity whose values are attacker-influencable."""
        return frozenset(
            name
            for name, f in cls.model_fields.items()
            if (f.json_schema_extra or {}).get("provenance") == "untrusted"
        )

    @classmethod
    def provenance_of(cls, field_name: str) -> Provenance:
        """Provenance of one field. Unknown fields report untrusted, failing closed."""
        f = cls.model_fields.get(field_name)
        if f is None:
            return "untrusted"
        return (f.json_schema_extra or {}).get("provenance", "untrusted")


# ---------------------------------------------------------------------------
# Core entities
# ---------------------------------------------------------------------------


class Customer(RazorpayEntity):
    id: str = trusted("cust_*")
    entity: str = "customer"
    name: str | None = untrusted("Customer-supplied display name", default=None)
    email: str | None = untrusted("Customer-supplied email", default=None)
    contact: str | None = untrusted("Customer-supplied phone", default=None)
    gstin: str | None = untrusted("Customer-supplied GSTIN", default=None)
    notes: dict[str, str] = untrusted("Free-form merchant metadata", default_factory=dict)
    created_at: int = trusted("Unix timestamp")


class Order(RazorpayEntity):
    id: str = trusted("order_*")
    entity: str = "order"
    amount: int = trusted("Amount in PAISE")
    amount_paid: int = trusted("Paise captured so far", default=0)
    amount_due: int = trusted("Paise outstanding", default=0)
    currency: str = trusted("ISO 4217", default="INR")
    receipt: str | None = untrusted("Merchant-supplied receipt reference", default=None)
    status: Literal["created", "attempted", "paid"] = trusted("Order state", default="created")
    attempts: int = trusted("Payment attempts", default=0)
    notes: dict[str, str] = untrusted("Free-form merchant metadata", default_factory=dict)
    created_at: int = trusted("Unix timestamp")


class Payment(RazorpayEntity):
    id: str = trusted("pay_*")
    entity: str = "payment"
    amount: int = trusted("Amount in PAISE")
    currency: str = trusted("ISO 4217", default="INR")
    status: Literal["created", "authorized", "captured", "refunded", "failed"] = trusted(
        "Payment state", default="captured"
    )
    order_id: str | None = trusted("Parent order", default=None)
    method: Literal["card", "upi", "netbanking", "wallet", "emi", "cardless_emi"] = trusted(
        "Instrument used", default="upi"
    )
    amount_refunded: int = trusted("Paise refunded to date", default=0)
    refund_status: Literal["partial", "full"] | None = trusted("Refund state", default=None)
    captured: bool = trusted("Whether funds were captured", default=True)
    international: bool = trusted("Cross-border flag", default=False)
    fee: int = trusted("Razorpay fee in paise", default=0)
    tax: int = trusted("Tax on fee in paise", default=0)
    description: str | None = untrusted("Merchant/payer-supplied description", default=None)
    email: str | None = untrusted("Payer-supplied email", default=None)
    contact: str | None = untrusted("Payer-supplied phone", default=None)
    vpa: str | None = untrusted("Payer-supplied UPI VPA -- an arbitrary string", default=None)
    bank: str | None = trusted("Issuing bank code", default=None)
    wallet: str | None = trusted("Wallet provider", default=None)
    card_id: str | None = trusted("Tokenised card reference", default=None)
    notes: dict[str, str] = untrusted("Free-form merchant metadata", default_factory=dict)
    error_code: str | None = trusted("Gateway error code", default=None)
    error_description: str | None = trusted("Gateway error text", default=None)
    created_at: int = trusted("Unix timestamp")


class Refund(RazorpayEntity):
    id: str = trusted("rfnd_*")
    entity: str = "refund"
    amount: int = trusted("Amount in PAISE")
    currency: str = trusted("ISO 4217", default="INR")
    payment_id: str = trusted("Payment being refunded")
    status: Literal["pending", "processed", "failed"] = trusted("Refund state", default="processed")
    speed_requested: Literal["normal", "optimum"] = trusted("Requested speed", default="normal")
    speed_processed: Literal["normal", "instant"] | None = trusted("Actual speed", default=None)
    receipt: str | None = untrusted("Merchant-supplied receipt reference", default=None)
    notes: dict[str, str] = untrusted("Free-form merchant metadata", default_factory=dict)
    created_at: int = trusted("Unix timestamp")


class DisputeEvidenceDocument(RazorpayEntity):
    """A dispute document. ``extracted_text`` is the OCR layer an agent reads."""

    id: str = trusted("doc_*")
    type: str = trusted("Document class, e.g. shipping_proof, customer_communication")
    extracted_text: str = untrusted("OCR text layer -- authored by an external party")


class Dispute(RazorpayEntity):
    id: str = trusted("disp_*")
    entity: str = "dispute"
    payment_id: str = trusted("Disputed payment")
    amount: int = trusted("Disputed amount in PAISE")
    currency: str = trusted("ISO 4217", default="INR")
    amount_deducted: int = trusted("Paise already debited from the merchant", default=0)
    reason_code: str = trusted("Network reason code, e.g. goods_not_received")
    respond_by: int = trusted("Deadline, unix timestamp")
    status: Literal["open", "under_review", "won", "lost", "closed"] = trusted(
        "Dispute state", default="open"
    )
    phase: Literal["fraud", "retrieval", "chargeback", "pre_arbitration", "arbitration"] = trusted(
        "Lifecycle phase", default="chargeback"
    )
    evidence: list[DisputeEvidenceDocument] = untrusted(
        "Counterparty-supplied evidence", default_factory=list
    )
    created_at: int = trusted("Unix timestamp")


class Settlement(RazorpayEntity):
    id: str = trusted("setl_*")
    entity: str = "settlement"
    amount: int = trusted("Settled amount in PAISE")
    status: Literal["created", "processed", "failed"] = trusted("State", default="processed")
    fees: int = trusted("Fees in paise", default=0)
    tax: int = trusted("Tax in paise", default=0)
    utr: str | None = trusted("Bank UTR", default=None)
    created_at: int = trusted("Unix timestamp")


class Payout(RazorpayEntity):
    """Money out. Unbounded by any prior payment."""

    id: str = trusted("pout_*")
    entity: str = "payout"
    fund_account_id: str = trusted("Destination fund account")
    amount: int = trusted("Amount in PAISE")
    currency: str = trusted("ISO 4217", default="INR")
    status: Literal[
        "queued", "pending", "processing", "processed", "reversed", "cancelled", "rejected"
    ] = trusted("Payout state", default="queued")
    purpose: str = trusted("Payout purpose, e.g. vendor_payment", default="vendor_payment")
    mode: Literal["IMPS", "NEFT", "RTGS", "UPI"] = trusted("Rail", default="IMPS")
    utr: str | None = trusted("Bank UTR", default=None)
    fees: int = trusted("Fees in paise", default=0)
    tax: int = trusted("Tax in paise", default=0)
    narration: str | None = untrusted("Beneficiary statement narration -- free text", default=None)
    reference_id: str | None = untrusted("Merchant-supplied reference", default=None)
    notes: dict[str, str] = untrusted("Free-form merchant metadata", default_factory=dict)
    failure_reason: str | None = trusted("Bank failure reason", default=None)
    created_at: int = trusted("Unix timestamp")


class PaymentLink(RazorpayEntity):
    id: str = trusted("plink_*")
    entity: str = "payment_link"
    amount: int = trusted("Amount in PAISE")
    currency: str = trusted("ISO 4217", default="INR")
    status: Literal["created", "partially_paid", "expired", "cancelled", "paid"] = trusted(
        "Link state", default="created"
    )
    description: str | None = untrusted(
        "Shown to the payer -- an egress channel for exfiltration", default=None
    )
    short_url: str | None = trusted("Razorpay-hosted URL", default=None)
    notes: dict[str, str] = untrusted("Free-form merchant metadata", default_factory=dict)
    created_at: int = trusted("Unix timestamp")


class SupportMessage(RazorpayEntity):
    """A support message. Not a Razorpay object; the refund agent reads it."""

    id: str = trusted("msg_*")
    entity: str = "support_message"
    payment_id: str | None = trusted("Linked payment, if any", default=None)
    author: Literal["customer", "agent", "system"] = trusted("Who wrote it")
    body: str = untrusted("Message text -- fully attacker-controlled when author=customer")
    created_at: int = trusted("Unix timestamp")


class InvoiceLineItem(RazorpayEntity):
    """A vendor invoice line. Every field is untrusted, ``amount`` included (D-010)."""

    name: str = untrusted("Vendor-supplied item name")
    description: str | None = untrusted("Vendor-supplied description", default=None)
    amount: int = untrusted("Vendor-stated line amount in PAISE")
    quantity: int = untrusted("Vendor-stated quantity", default=1)


class Invoice(RazorpayEntity):
    """A vendor invoice. Counterparty-authored except ``fund_account_id`` (D-010)."""

    id: str = trusted("inv_*")
    entity: str = "invoice"
    invoice_number: str = untrusted("Vendor-supplied invoice number")
    vendor_name: str = untrusted("Vendor-supplied name")
    fund_account_id: str = trusted("Destination from the merchant's vendor master")
    amount: int = untrusted("Vendor-stated total in PAISE")
    currency: str = trusted("ISO 4217", default="INR")
    status: Literal["issued", "approved", "paid", "cancelled"] = trusted(
        "Approval state, set by the merchant", default="approved"
    )
    line_items: list[InvoiceLineItem] = untrusted("Vendor-supplied lines", default_factory=list)
    remittance_advice: str | None = untrusted(
        "Free-text payment instructions written by the vendor", default=None
    )
    notes: dict[str, str] = untrusted("Free-form metadata", default_factory=dict)
    created_at: int = trusted("Unix timestamp")


ENTITY_TYPES: dict[str, type[RazorpayEntity]] = {
    "customer": Customer,
    "invoice": Invoice,
    "order": Order,
    "payment": Payment,
    "refund": Refund,
    "dispute": Dispute,
    "settlement": Settlement,
    "payout": Payout,
    "payment_link": PaymentLink,
    "support_message": SupportMessage,
}


def untrusted_field_registry() -> dict[str, frozenset[str]]:
    """Entity type -> untrusted field names, for the gateway's taint tracker."""
    return {name: cls.untrusted_fields() for name, cls in ENTITY_TYPES.items()}
