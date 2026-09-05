from pydantic import BaseModel, Field, confloat
from typing import Literal, Optional

class Variant(BaseModel):
    variant_id: str
    attribute: str
    value: str
    price_delta: Optional[float] = 0.0
    stock_count: Optional[int] = None
    availability: Optional[Literal["in_stock", "out_of_stock", "preorder"]] = None

class Price(BaseModel):
    amount: float = Field(gt=0)
    currency: str = "INR"

class Metadata(BaseModel):
    source_confidence: confloat(ge=0, le=1)
    extraction_notes: Optional[str] = None

class Product(BaseModel):
    product_id: str
    name: str
    category: str
    description: str
    price: Price
    availability: Literal["in_stock", "out_of_stock", "preorder"]
    variants: Optional[list[Variant]] = []
    tags: Optional[list[str]] = []
    metadata: Metadata
# --- Append this below your existing Product schema in schema.py ---

class QueryIntent(BaseModel):
    """
    Structured representation of what the buyer wants, parsed from free text
    by the LLM. This is the contract between 'natural language in' and
    'repository query out' — keeping this explicit (rather than having the
    LLM directly generate code or DB calls) is what makes the agent safe
    and auditable: we can always inspect exactly what the agent understood
    before it touches the data.
    """
    keyword: Optional[str] = None
    min_price: Optional[float] = None
    max_price: Optional[float] = None
    variant_attribute: Optional[str] = None   
    variant_value: Optional[str] = None       
    reasoning: str = Field(description="Brief explanation of how the query was interpreted")