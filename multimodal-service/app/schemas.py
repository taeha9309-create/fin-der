"""HTTP contracts for the multimodal service."""
from __future__ import annotations
from typing import Any, Literal
from pydantic import AliasChoices, BaseModel, ConfigDict, Field

Verdict = Literal["NORMAL", "SUSPICIOUS", "PHISHING", "UNKNOWN"]

class PageData(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)
    title: str = Field(default="", max_length=1000)
    visible_text: str = Field(default="", validation_alias=AliasChoices("visibleText", "visible_text", "text"))
    html: str = ""

class CollectedObject(BaseModel):
    model_config = ConfigDict(extra="allow")

class NetworkData(BaseModel):
    model_config = ConfigDict(extra="allow")

class AnalyzeRequest(BaseModel):
    """Accept the canonical nested payload and the former flat payload."""
    model_config = ConfigDict(extra="ignore", populate_by_name=True)
    analysis_id: str | None = Field(default=None, validation_alias=AliasChoices("analysisId", "analysis_id"))
    requested_url: str | None = Field(default=None, max_length=4096, validation_alias=AliasChoices("requestedUrl", "requested_url", "url", "original_url"))
    final_url: str | None = Field(default=None, max_length=4096, validation_alias=AliasChoices("finalUrl", "final_url"))
    status_code: int | None = Field(default=None, validation_alias=AliasChoices("statusCode", "status_code"))
    page: PageData | None = None
    title: str = Field(default="", max_length=1000)
    visible_text: str = Field(default="", validation_alias=AliasChoices("visibleText", "visible_text", "text", "page_text"))
    html: str = ""
    inputs: list[CollectedObject] = Field(default_factory=list)
    forms: list[CollectedObject] = Field(default_factory=list)
    links: list[CollectedObject] = Field(default_factory=list)
    network: NetworkData | None = None
    redirect_chain: list[Any] = Field(default_factory=list, validation_alias=AliasChoices("redirectChain", "redirect_chain"))
    screenshot: str | dict[str, Any] | None = Field(default=None, validation_alias=AliasChoices("screenshot", "screenshotBase64", "screenshot_base64"))
    error: str | None = None

    def page_values(self) -> tuple[str, str, str]:
        if self.page is None:
            return self.title, self.visible_text, self.html
        return self.page.title or self.title, self.page.visible_text or self.visible_text, self.page.html or self.html

class Impersonation(BaseModel):
    detected: bool
    brand: str | None
    category: str | None
class CredentialIntent(BaseModel):
    detected: bool
    types: list[str]
class DomainAnalysis(BaseModel):
    currentDomain: str | None
    officialDomains: list[str]
    domainBrandMismatch: bool
class BehaviorAnalysis(BaseModel):
    financialActionRequest: bool
    externalContactRequest: bool
    downloadRequest: bool
class AnalyzeResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    analysisId: str
    pageRiskScore: int = Field(ge=0, le=100, strict=True)
    verdict: Verdict
    impersonation: Impersonation
    credentialIntent: CredentialIntent
    domainAnalysis: DomainAnalysis
    behaviorAnalysis: BehaviorAnalysis
    detectedSignals: list[str]
    reasons: list[str]
    confidence: float = Field(ge=0, le=1)
