"""Import all models so they register on the shared declarative Base."""
from app.models.user import User, UserRole  # noqa: F401
from app.models.hostel import (  # noqa: F401
    Hostel, Block, Floor, Room, BedSpace,
    HostelCategory, AccommodationStatus, RoomType, BedStatus,
)
from app.models.student import Student, Gender, StudentStatus  # noqa: F401
from app.models.application import (  # noqa: F401
    Application, HostelPreference, ApplicationStatus,
    EligibilityStatus, RequirementVerificationStatus,
)
from app.models.priority import (  # noqa: F401
    PriorityCriterion, PreferenceScoreConfig, PenaltyConfig,
    RuleSetVersion, StudentPriorityScore, PriorityScoreDetail,
)
from app.models.optimization import (  # noqa: F401
    OptimizationRun, OptimizationStatus, UnallocatedRecord, UnallocatedReason,
)
from app.models.allocation import (  # noqa: F401
    AllocationResult, AllocationStatus, AllocationHistory, WaitlistEntry,
)
from app.models.notification import Notification  # noqa: F401
from app.models.audit import AuditLog  # noqa: F401
