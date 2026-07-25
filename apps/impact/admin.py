from django.contrib import admin

from .models import (
    BusinessImpactProfile,
    ImpactAssumptionRevision,
    ImpactBaseline,
    ImpactDataSource,
    ImpactMetricSnapshot,
    ImpactOpportunity,
    ImpactReport,
    SiteImpactProfile,
)

admin.site.register(BusinessImpactProfile)
admin.site.register(SiteImpactProfile)
admin.site.register(ImpactAssumptionRevision)
admin.site.register(ImpactDataSource)
admin.site.register(ImpactBaseline)
admin.site.register(ImpactMetricSnapshot)
admin.site.register(ImpactOpportunity)
admin.site.register(ImpactReport)
