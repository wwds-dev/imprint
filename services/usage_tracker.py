from datetime import datetime
from services.providers import is_local as is_local_provider
from services.database import get_connection

# Every backend that costs money. The cloud flag used to hardcode only
# {"openai", "deepseek", "gemini"}, so Anthropic, Kimi, Qwen and Higgsfield
# requests were recorded as local (cloud=0) in the usage table.
CLOUD_BACKENDS = {"openai", "deepseek", "gemini", "anthropic", "kimi", "qwen",
                  "higgsfield"}


def _eur_per_usd(conn) -> float:
    # The one reader per-unit pricing uses too: a rate that is not a finite
    # number above zero falls back, so a typo in Settings can no longer make
    # every text request free or negative (security review P2-2).
    from services.per_unit_pricing import eur_per_usd
    return eur_per_usd(conn)


def _row_cost_usd(row, input_tokens: int, output_tokens: int,
                  cached_input_tokens: int = 0) -> float:
    """One request's USD cost on one pricing row."""
    full_rate = row["input_per_1m_usd"]
    cached_rate = row["cached_input_per_1m_usd"] or full_rate
    # Clamp: a provider reporting more cached than prompt tokens must not
    # produce a negative full-rate slice.
    cached = max(0, min(int(cached_input_tokens or 0), input_tokens))
    uncached = input_tokens - cached
    input_usd = ((uncached / 1_000_000) * full_rate
                 + (cached / 1_000_000) * cached_rate)
    output_usd = (output_tokens / 1_000_000) * row["output_per_1m_usd"]
    return input_usd + output_usd


def estimate_input_tokens(messages) -> int:
    """Input tokens for the messages a request will send: chars/4 over every
    message's text — system prompt, context, history and project
    instructions, not just the user's own prompt (audit B-F2)."""
    chars = 0
    for message in messages or ():
        content = message.get("content") if isinstance(message, dict) else message
        chars += len(str(content or ""))
    return max(1, chars // 4)


def max_cost_eur(backend: str, model: str, in_tokens: int,
                 conn=None) -> float | None:
    """The most one text request can cost: its input plus the full output
    reserve (services/output_limits.reserved_output_tokens) at the output
    rate. None when the model has no price; 0.0 for local models.

    The request guard, the Chat estimate and the recommendation engine's
    budget rule all call this, so the three agree on the euros (spec B-F2 b).
    """
    from services.output_limits import reserved_output_tokens
    from services.pricing_catalog import resolve_price_row

    if is_local_provider(backend):
        return 0.0
    own = conn is None
    if own:
        conn = get_connection()
    try:
        row, _source = resolve_price_row(conn, backend, model)
        rate = _eur_per_usd(conn)
    finally:
        if own:
            conn.close()
    if not row:
        return None
    usd = _row_cost_usd(row, int(in_tokens),
                        reserved_output_tokens(backend, model))
    return round(usd * rate, 6)


class UsageTracker:
    def estimate_tokens(self, prompt_text: str, response_text: str) -> tuple[int, int]:
        return max(1, len(prompt_text) // 4), max(1, len(response_text) // 4)

    def normalize_usage(self, usage: dict | None, prompt_text: str, response_text: str) -> tuple[int, int, str]:
        if not usage:
            i, o = self.estimate_tokens(prompt_text, response_text)
            return i, o, "estimated"

        override = usage.get("cost_type_override")

        i = int(usage.get("input_tokens") or usage.get("prompt_tokens") or usage.get("prompt_token_count") or 0)
        o = int(usage.get("output_tokens") or usage.get("completion_tokens") or usage.get("candidates_token_count") or 0)

        if i <= 0 or o <= 0:
            ei, eo = self.estimate_tokens(prompt_text, response_text)
            return i or ei, o or eo, override or "mixed"

        return i, o, override or "exact"

    def load_pricing(self) -> dict:
        with get_connection() as conn:
            result = {"eur_per_usd": _eur_per_usd(conn)}

            for r in conn.execute(
                "SELECT backend, model, input_per_1m_usd, output_per_1m_usd, "
                "cached_input_per_1m_usd FROM pricing"
            ):
                backend = r["backend"]
                result.setdefault(backend, {})
                result[backend][r["model"]] = {
                    "input_per_1m_usd": r["input_per_1m_usd"],
                    "output_per_1m_usd": r["output_per_1m_usd"],
                    "cached_input_per_1m_usd": r["cached_input_per_1m_usd"],
                }
        return result

    def calculate_cost_eur(self, backend: str, model: str, input_tokens: int,
                           output_tokens: int, cached_input_tokens: int = 0) -> float:
        """Cost of one request in EUR.

        `cached_input_tokens` is the slice of `input_tokens` the provider served
        from its prompt cache; it bills at the model's cached rate, which is
        heavily discounted (Kimi charges 0.19 against 0.95 per 1M). When no
        cached rate is known the slice bills at the full input rate, so an
        unknown provider is never under-estimated.
        """
        if is_local_provider(backend):
            return 0.0

        with get_connection() as conn:
            eur_per_usd = _eur_per_usd(conn)

            # Exact row, else the row of the model this one is a dated
            # snapshot or alias of, else the provider default.
            from services.pricing_catalog import resolve_price_row
            row, _source = resolve_price_row(conn, backend, model)

        if not row:
            return 0.0

        usd = _row_cost_usd(row, input_tokens, output_tokens, cached_input_tokens)
        return round(usd * eur_per_usd, 6)

    def log_request(self, agent: str, backend: str, model: str,
                    prompt_text: str, response_text: str, usage: dict | None = None,
                    flat_cost_eur: float | None = None,
                    project: str | None = None,
                    cost_type: str | None = None) -> dict:
        """Record one request and what it cost.

        `flat_cost_eur` is for work that is **not billed per token**: an image,
        a video render, a thousand characters of speech. The cost model here is
        token-denominated and cannot express any of those, which is why image
        generation, Higgsfield renders and TTS were all counting as €0.00
        against the session and daily caps no matter how much they cost. A
        caller that knows the real price passes it, and the token arithmetic is
        skipped rather than fudged. `cost_type` names such an amount when it
        is not a per-unit price: "partial" is what a failed or stopped render
        or batch had already spent (GodAI.record_partial).
        """
        input_tokens, output_tokens, token_cost_type = self.normalize_usage(
            usage, prompt_text, response_text)
        cached_input_tokens = int((usage or {}).get("cached_input_tokens") or 0)
        if flat_cost_eur is not None:
            cost_eur = round(float(flat_cost_eur), 6)
            cost_type = cost_type or "per_unit"
        else:
            cost_type = token_cost_type
            cost_eur = self.calculate_cost_eur(
                backend, model, input_tokens, output_tokens, cached_input_tokens)
        timestamp = datetime.now().isoformat(timespec="seconds")

        with get_connection() as conn:
            conn.execute("""
                INSERT INTO usage
                  (timestamp, agent, backend, model, input_tokens, output_tokens,
                   total_tokens, cost_eur, cost_type, cloud, project)
                VALUES (?,?,?,?,?,?,?,?,?,?,?)
            """, (
                timestamp, agent, backend, model,
                input_tokens, output_tokens, input_tokens + output_tokens,
                cost_eur, cost_type,
                1 if backend in CLOUD_BACKENDS else 0,
                project or "",
            ))
            conn.commit()

        return {
            "timestamp": timestamp,
            "agent": agent,
            "backend": backend,
            "model": model,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": input_tokens + output_tokens,
            "cost_eur": cost_eur,
            "estimated_cost": cost_eur,
            "cost_type": cost_type,
            "cloud": backend in CLOUD_BACKENDS,
            "project": project or "",
        }

    def get_project_today_total(self, project: str) -> float:
        today = datetime.now().date().isoformat()
        with get_connection() as conn:
            row = conn.execute(
                "SELECT COALESCE(SUM(cost_eur), 0.0) AS total FROM usage "
                "WHERE project = ? AND timestamp LIKE ?",
                (project, f"{today}%"),
            ).fetchone()
        return round(float(row["total"]), 6)

    def get_today_total(self) -> float:
        today = datetime.now().date().isoformat()
        with get_connection() as conn:
            row = conn.execute(
                "SELECT COALESCE(SUM(cost_eur), 0.0) AS total FROM usage WHERE timestamp LIKE ?",
                (f"{today}%",)
            ).fetchone()
        return round(float(row["total"]), 6)

    def get_agent_today_total(self, agent: str) -> float:
        """Today's spend for one agent — feeds the per-agent daily cap."""
        today = datetime.now().date().isoformat()
        with get_connection() as conn:
            row = conn.execute(
                "SELECT COALESCE(SUM(cost_eur), 0.0) AS total FROM usage "
                "WHERE timestamp LIKE ? AND agent = ?",
                (f"{today}%", agent)
            ).fetchone()
        return round(float(row["total"]), 6)

    def get_total_requests_today(self) -> int:
        today = datetime.now().date().isoformat()
        with get_connection() as conn:
            row = conn.execute(
                "SELECT COUNT(*) AS cnt FROM usage WHERE timestamp LIKE ?",
                (f"{today}%",)
            ).fetchone()
        return int(row["cnt"])

    def load_log(self) -> list:
        with get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM usage ORDER BY id ASC"
            ).fetchall()
        return [dict(r) for r in rows]
