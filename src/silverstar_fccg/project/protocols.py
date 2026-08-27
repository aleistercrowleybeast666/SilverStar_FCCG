from __future__ import annotations

from dataclasses import dataclass

from silverstar_fccg.plugins.catalog import PluginCatalog
from silverstar_fccg.plugins.manifest import (
    PROTOCOL_PROFILE_SLOTS,
    ProtocolProfileContribution,
    TransportContribution,
)
from silverstar_fccg.project.model import ProjectModel


PROTOCOL_SERVICES = {
    "telemetry": "telemetry_service",
    "maintenance": "maintenance_service",
    "logging": "flight_log_service",
}

PROTOCOL_BINDINGS = {
    "telemetry": "telemetry_transport",
    "maintenance": "maintenance_console",
    "logging": "flight_log_sink",
}


@dataclass(frozen=True, slots=True)
class ProtocolProfileSelection:
    category: str
    bundle_id: str
    profile: ProtocolProfileContribution


@dataclass(frozen=True, slots=True)
class ProtocolTransportProvider:
    component_id: str
    instance_id: str
    transport: TransportContribution


@dataclass(frozen=True, slots=True)
class ProtocolBinding:
    category: str
    service: str
    slot: str
    profile_id: str
    binding: str
    provider_component: str
    provider_instance: str
    transport_capability: str


@dataclass(frozen=True, slots=True)
class ProtocolResolutionIssue:
    code: str
    message: str


@dataclass(frozen=True, slots=True)
class ProtocolResolution:
    selections: tuple[ProtocolProfileSelection, ...]
    bindings: tuple[ProtocolBinding, ...]
    issues: tuple[ProtocolResolutionIssue, ...]

    @property
    def valid(self) -> bool:
        return not self.issues


def ProtocolProfileSelections_Get(
    model: ProjectModel, catalog: PluginCatalog
) -> tuple[ProtocolProfileSelection, ...]:
    selections: list[ProtocolProfileSelection] = []
    for category, profile_id in sorted(model.protocol_profiles.items()):
        for bundle_id in model.protocol_bundles:
            contribution = catalog.Component_Get(bundle_id).protocol
            if contribution is None:
                continue
            selections.extend(
                ProtocolProfileSelection(category, bundle_id, profile)
                for profile in contribution.profiles.get(category, ())
                if profile.profile_id == profile_id
            )
    return tuple(selections)


def ProtocolTransportProviders_Get(
    model: ProjectModel, catalog: PluginCatalog
) -> tuple[ProtocolTransportProvider, ...]:
    providers: list[ProtocolTransportProvider] = []
    for instance in model.device_instances:
        manifest = catalog.Component_Get(instance.plugin)
        providers.extend(
            ProtocolTransportProvider(
                component_id=manifest.component_id,
                instance_id=instance.instance_id,
                transport=transport,
            )
            for transport in manifest.transports
        )
    if model.hardware.mode == "board_plugin" and model.board:
        board = catalog.Component_Get(model.board)
        providers.extend(
            ProtocolTransportProvider(
                component_id=board.component_id,
                instance_id=board.component_id,
                transport=transport,
            )
            for transport in board.transports
        )
    return tuple(providers)


def _TransportCompatible_Is(requirement, provider: TransportContribution) -> bool:
    return (
        provider.capability == requirement.capability
        and provider.kind == requirement.kind
        and provider.mode == requirement.mode
        and provider.mtu >= requirement.minimum_mtu
        and (not requirement.ordered or provider.ordered)
        and (not requirement.bidirectional or provider.bidirectional)
        and (not requirement.reliable or provider.reliable)
    )


def ProtocolResolution_Resolve(
    model: ProjectModel, catalog: PluginCatalog
) -> ProtocolResolution:
    selections = ProtocolProfileSelections_Get(model, catalog)
    providers = ProtocolTransportProviders_Get(model, catalog)
    issues: list[ProtocolResolutionIssue] = []
    bindings: list[ProtocolBinding] = []

    selected_by_category: dict[str, list[ProtocolProfileSelection]] = {}
    for selection in selections:
        selected_by_category.setdefault(selection.category, []).append(selection)

    declared_categories = {
        category
        for bundle_id in model.protocol_bundles
        for protocol in (catalog.Component_Get(bundle_id).protocol,)
        if protocol is not None
        for category in protocol.profiles
    }
    if set(model.protocol_profiles) != declared_categories:
        issues.append(
            ProtocolResolutionIssue(
                "protocol_profile_categories",
                "Protocol profile categories do not match the selected bundles",
            )
        )

    for category, profile_id in sorted(model.protocol_profiles.items()):
        matches = selected_by_category.get(category, [])
        if len(matches) != 1:
            issues.append(
                ProtocolResolutionIssue(
                    "protocol_profile",
                    f"Protocol profile {category}/{profile_id} resolves to "
                    f"{len(matches)} complete implementations",
                )
            )
            continue
        selection = matches[0]
        profile = selection.profile
        if (
            profile.service != PROTOCOL_SERVICES.get(category)
            or profile.slot != PROTOCOL_PROFILE_SLOTS.get(category)
            or profile.binding != PROTOCOL_BINDINGS.get(category)
        ):
            issues.append(
                ProtocolResolutionIssue(
                    "protocol_layers",
                    f"Protocol profile {category}/{profile.profile_id} has an "
                    "invalid Service, Slot, or Transport Binding declaration",
                )
            )
            continue
        requirement = profile.transport
        if requirement is None:
            issues.append(
                ProtocolResolutionIssue(
                    "protocol_transport",
                    f"Protocol profile {category}/{profile.profile_id} has no "
                    "transport constraint",
                )
            )
            continue
        compatible = tuple(
            provider
            for provider in providers
            if _TransportCompatible_Is(requirement, provider.transport)
        )
        if not compatible:
            issues.append(
                ProtocolResolutionIssue(
                    "protocol_transport",
                    f"Protocol profile {category}/{profile.profile_id} requires "
                    f"{requirement.capability} ({requirement.kind}, "
                    f"{requirement.mode}, MTU >= {requirement.minimum_mtu})",
                )
            )
            continue
        if len(compatible) > 1:
            issues.append(
                ProtocolResolutionIssue(
                    "protocol_transport_ambiguous",
                    f"Protocol profile {category}/{profile.profile_id} has "
                    f"multiple compatible physical transports: "
                    + ", ".join(provider.instance_id for provider in compatible),
                )
            )
            continue
        provider = compatible[0]
        bindings.append(
            ProtocolBinding(
                category=category,
                service=profile.service,
                slot=profile.slot,
                profile_id=profile.profile_id,
                binding=profile.binding,
                provider_component=provider.component_id,
                provider_instance=provider.instance_id,
                transport_capability=provider.transport.capability,
            )
        )
    return ProtocolResolution(
        selections=selections,
        bindings=tuple(bindings),
        issues=tuple(issues),
    )
