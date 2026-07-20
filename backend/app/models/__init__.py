"""SQLAlchemy 模型集合。

导入各模块以触发表注册到 Base.metadata。
"""
from app.models.analysis import AnalysisJob, JobItem, StageRecord
from app.models.article import DailyArticle
from app.models.email import Email
from app.models.opencode_config import OpenCodeConfig, SkillConfig
from app.models.subscription import Subscription
from app.models.user import User

__all__ = [
    "User",
    "Email",
    "AnalysisJob",
    "StageRecord",
    "JobItem",
    "DailyArticle",
    "Subscription",
    "OpenCodeConfig",
    "SkillConfig",
]
