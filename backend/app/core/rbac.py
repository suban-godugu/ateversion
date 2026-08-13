from __future__ import annotations

from enum import Enum


class Role(str, Enum):
    VIEWER = "VIEWER"
    TEST_ENGINEER = "TEST_ENGINEER"
    PROCESS_ENGINEER = "PROCESS_ENGINEER"
    AI_ENGINEER = "AI_ENGINEER"
    MAINTENANCE_ENGINEER = "MAINTENANCE_ENGINEER"
    ADMIN = "ADMIN"


class Permission(str, Enum):
    # Read surfaces
    READ_DASHBOARD = "read:dashboard"
    READ_WAFER = "read:wafer"
    READ_EVENTS = "read:events"
    READ_KPIS = "read:kpis"
    READ_MAINTENANCE = "read:maintenance"
    READ_LIMITS = "read:limits"
    READ_TELEMETRY = "read:telemetry"
    READ_AGGREGATIONS = "read:aggregations"

    # Mutations
    ACK_EVENTS = "write:events:ack"
    WRITE_TELEMETRY = "write:telemetry"
    RECOMMEND_LIMITS = "write:limits:recommend"
    APPROVE_LIMITS = "write:limits:approve"
    REJECT_LIMITS = "write:limits:reject"
    ROLLBACK_LIMITS = "write:limits:rollback"
    RUN_MAINTENANCE_PREDICT = "write:maintenance:predict"
    WRITE_KPI = "write:kpis"
    MANAGE_USERS = "manage:users"
    STREAM_WS = "stream:ws"


ROLE_PERMISSIONS: dict[Role, set[Permission]] = {
    Role.VIEWER: {
        Permission.READ_DASHBOARD,
        Permission.READ_WAFER,
        Permission.READ_EVENTS,
        Permission.READ_KPIS,
        Permission.READ_MAINTENANCE,
        Permission.READ_LIMITS,
        Permission.READ_AGGREGATIONS,
        Permission.STREAM_WS,
    },
    Role.TEST_ENGINEER: set(),  # filled below
    Role.PROCESS_ENGINEER: set(),
    Role.AI_ENGINEER: set(),
    Role.MAINTENANCE_ENGINEER: set(),
    Role.ADMIN: set(Permission),
}

ROLE_PERMISSIONS[Role.TEST_ENGINEER] = ROLE_PERMISSIONS[Role.VIEWER] | {
    Permission.ACK_EVENTS,
    Permission.WRITE_TELEMETRY,
    Permission.READ_TELEMETRY,
}

ROLE_PERMISSIONS[Role.PROCESS_ENGINEER] = ROLE_PERMISSIONS[Role.TEST_ENGINEER] | {
    Permission.RECOMMEND_LIMITS,
    Permission.APPROVE_LIMITS,
    Permission.REJECT_LIMITS,
    Permission.ROLLBACK_LIMITS,
}

ROLE_PERMISSIONS[Role.AI_ENGINEER] = ROLE_PERMISSIONS[Role.VIEWER] | {
    Permission.RUN_MAINTENANCE_PREDICT,
    Permission.WRITE_KPI,
    Permission.READ_TELEMETRY,
    Permission.RECOMMEND_LIMITS,
}

ROLE_PERMISSIONS[Role.MAINTENANCE_ENGINEER] = ROLE_PERMISSIONS[Role.VIEWER] | {
    Permission.RUN_MAINTENANCE_PREDICT,
    Permission.ACK_EVENTS,
}


def permissions_for(role: Role | str) -> set[Permission]:
    r = Role(role) if not isinstance(role, Role) else role
    return set(ROLE_PERMISSIONS.get(r, set()))


def has_permission(role: Role | str, permission: Permission) -> bool:
    return permission in permissions_for(role)
