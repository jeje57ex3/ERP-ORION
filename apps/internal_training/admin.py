from django.contrib import admin
from .models import (
    TrainingCourse, TrainingChapter, TrainingPage,
    TrainingPageBlock, TrainingEnrollment, TrainingPageProgress,
)


class TrainingChapterInline(admin.TabularInline):
    model = TrainingChapter
    extra = 0
    fields = ('title', 'order')


class TrainingPageInline(admin.TabularInline):
    model = TrainingPage
    extra = 0
    fields = ('title', 'order', 'status')


class TrainingPageBlockInline(admin.TabularInline):
    model = TrainingPageBlock
    extra = 0
    fields = ('block_type', 'order', 'content', 'file')


@admin.register(TrainingCourse)
class TrainingCourseAdmin(admin.ModelAdmin):
    list_display = ('title', 'company', 'status', 'chapters_count', 'enrolled_count', 'created_at')
    list_filter = ('status', 'company')
    search_fields = ('title', 'description')
    inlines = [TrainingChapterInline]
    readonly_fields = ('created_at', 'updated_at')


@admin.register(TrainingChapter)
class TrainingChapterAdmin(admin.ModelAdmin):
    list_display = ('title', 'course', 'order', 'pages_count')
    list_filter = ('course__company',)
    search_fields = ('title',)
    inlines = [TrainingPageInline]


@admin.register(TrainingPage)
class TrainingPageAdmin(admin.ModelAdmin):
    list_display = ('title', 'chapter', 'order', 'status')
    list_filter = ('status', 'chapter__course__company')
    search_fields = ('title',)
    inlines = [TrainingPageBlockInline]


@admin.register(TrainingEnrollment)
class TrainingEnrollmentAdmin(admin.ModelAdmin):
    list_display = ('user', 'course', 'enrolled_at', 'is_completed')
    list_filter = ('course__company',)
    search_fields = ('user__username', 'course__title')


@admin.register(TrainingPageProgress)
class TrainingPageProgressAdmin(admin.ModelAdmin):
    list_display = ('user', 'page', 'is_completed', 'completed_at')
    list_filter = ('is_completed',)
