from dataclasses import dataclass
from decimal import Decimal

from services import money_text
from services.registry import Registry


def _money(value: float | int | str) -> Decimal:
    """Exact decimal for a euro amount, to the micro-euro.

    Via `str` on purpose: `Decimal(0.1)` keeps the binary error the float
    already carries, while `Decimal(str(0.1))` is exactly 0.1. Without this,
    `1.00 - 0.90` is 0.09999999999999998 and a request estimated at exactly the
    remaining budget is refused — safe, but wrong, and confusing to hit.

    Rounded to six places first, as services/money_text does before it words
    a figure: a session total summed in floats (0.1 + 0.2 + 0.27 is
    0.5700000000000001) otherwise refused a €0.43 request against "€0.43
    left", two equal figures in one refusal.
    """
    return Decimal(str(round(float(value), 6)))


def _not_sent(estimated_cost, where: str, remedy: str) -> str:
    """A budget refusal, worded from the figures the check compared.

    Nothing has been spent at this point, so it never says "exceeded" (the
    old wording did). And it never suggests a shorter prompt: output is
    reserved at the length limit whatever the prompt, so shortening one
    barely moves the figure (spec Design, "B-F2 refusal").
    """
    return (f"Not sent: this request can cost up to "
            f"{money_text.up_to(estimated_cost)} and {where}. {remedy}")


@dataclass
class ValidationResult:
    allowed: bool
    reason: str
    # Which rule refused, machine-readable — consumers must never classify
    # a refusal by substring-matching the human sentence (the project cap's
    # wording contains "daily budget" and misled exactly such a match).
    # "" when allowed; else one of: agent_disabled, tool_disabled,
    # permission, agent_cap, project_cap, session_cap, daily_cap, approval.
    scope: str = ""


class Validator:
    """
    Central permission gate. Called before any agent/tool runs.
    All checks return ValidationResult(allowed, reason).
    """

    def __init__(self, registry: Registry):
        self.registry = registry

    def validate(
        self,
        agent_name: str,
        tool_name: str,
        provider: str,
        api_permissions: dict[str, bool],
        session_cost: float,
        session_budget: float,
        daily_cost: float,
        daily_budget: float,
        estimated_cost: float,
        project_name: str = "",
        project_cost: float = 0.0,
        project_budget: float | None = None,
        agent_daily_cost: float = 0.0,
    ) -> ValidationResult:
        # 1. Agent enabled?
        if not self.registry.is_agent_enabled(agent_name):
            return ValidationResult(False, f"Agent '{agent_name}' is disabled in the registry.")

        # 2. Tool enabled? (skip for audiobook which has no tool)
        if tool_name and not self.registry.is_tool_enabled(tool_name):
            return ValidationResult(False, f"Tool '{tool_name}' is disabled in the registry.")

        # 3. Provider allowed for this agent?
        if not self.registry.agent_allows_provider(agent_name, provider):
            return ValidationResult(
                False,
                f"Agent '{agent_name}' does not permit provider '{provider}'."
            )

        # 4. Provider allowed for this tool?
        if tool_name and not self.registry.tool_allows_provider(tool_name, provider):
            return ValidationResult(
                False,
                f"Tool '{tool_name}' does not permit provider '{provider}'."
            )

        # 5. Tool allowed for this agent?
        if tool_name and not self.registry.agent_allows_tool(agent_name, tool_name):
            return ValidationResult(
                False,
                f"Agent '{agent_name}' does not permit tool '{tool_name}'."
            )

        # 6. API checkbox permission (free pass for ollama)
        if provider != "ollama":
            perm_key = f"allow_{provider}"
            if not api_permissions.get(perm_key, False):
                return ValidationResult(
                    False,
                    f"API access for '{provider}' is not enabled. Enable it in the API Permissions panel."
                )

        # 7-9 compare money, so they work in Decimal rather than float.
        estimated = _money(estimated_cost)

        # 7. Per-agent budget (daily). Accumulates the agent's spend today:
        # the earlier per-request comparison let a €1.00/day agent issue
        # €0.99 requests without limit while the refusal message claimed a
        # daily cap. Callers that cannot supply the day's spend pass 0 and
        # get the old per-request behaviour.
        agent_budget = self.registry.get_agent_budget(agent_name)
        if agent_budget is not None and provider != "ollama":
            if estimated + _money(agent_daily_cost) > _money(agent_budget):
                return ValidationResult(
                    False,
                    _not_sent(estimated_cost,
                              f"Agent '{agent_name}' has "
                              f"{money_text.left(_money(agent_budget) - _money(agent_daily_cost))} "
                              f"left today (of {money_text.paid(agent_budget)})",
                              "Pick a cheaper or local model."),
                    scope="agent_cap",
                )

        # 8. Optional daily cap for the currently selected project.
        if project_budget is not None and provider != "ollama":
            project_remaining = _money(project_budget) - _money(project_cost)
            if estimated > project_remaining:
                return ValidationResult(
                    False,
                    _not_sent(estimated_cost,
                              f"Project '{project_name}' has "
                              f"{money_text.left(project_remaining)} left today "
                              f"(of {money_text.paid(project_budget)})",
                              "Pick a cheaper or local model."),
                    scope="project_cap",
                )

        # 9. Session budget
        if provider != "ollama":
            session_remaining = _money(session_budget) - _money(session_cost)
            if estimated > session_remaining:
                return ValidationResult(
                    False,
                    _not_sent(estimated_cost,
                              f"your session cap has "
                              f"{money_text.left(session_remaining)} left "
                              f"(of {money_text.paid(session_budget)})",
                              "Pick a cheaper or local model, or raise Session € "
                              "under Limits and press Save Limits."),
                    scope="session_cap",
                )

        # 10. Daily budget
        if provider != "ollama":
            daily_remaining = _money(daily_budget) - _money(daily_cost)
            if estimated > daily_remaining:
                return ValidationResult(
                    False,
                    _not_sent(estimated_cost,
                              f"today's cap has "
                              f"{money_text.left(daily_remaining)} left "
                              f"(of {money_text.paid(daily_budget)})",
                              "Pick a cheaper or local model, raise Daily € "
                              "under Limits, or wait until tomorrow."),
                    scope="daily_cap",
                )

        # 11. Approval required?
        if self.registry.agent_requires_approval(agent_name):
            return ValidationResult(
                False,
                f"Agent '{agent_name}' requires manual approval before running."
            )

        return ValidationResult(True, "OK")
