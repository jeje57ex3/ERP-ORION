from django.contrib import admin
from .models import (
    TrainingCourse, TrainingChapter, TrainingPage,
    TrainingPageBlock, TrainingEnrollment, TrainingPageProgress,
    ChoixDeQuestion, Competence, QuestionDeQuiz, Quiz, TentativeDeQuiz,
    ValidationTerrain,
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


# ── Parcours : quiz, compétences, validations ────────────────────────────────
#
# POURQUOI L'ADMIN DJANGO ICI, ET PAS UN ÉCRAN DÉDIÉ
#
# La règle de cet ERP est qu'une fonction d'administration se pilote depuis
# l'interface, jamais depuis un terminal. L'admin Django EST une interface,
# déjà reliée au menu (Réglages → Administration), déjà protégée par les
# droits. Un constructeur de quiz dédié serait plus agréable ; il n'est pas
# nécessaire pour que la fonction soit utilisable, et sans ces quelques
# lignes un quiz ne serait créable qu'en console — c'est-à-dire pas du tout.
#
# Les écrans de l'apprenant et du valideur, eux, sont des pages de l'ERP :
# voir apps/internal_training/views.py.


class ChoixDeQuestionInline(admin.TabularInline):
    model = ChoixDeQuestion
    extra = 3
    fields = ('order', 'libelle', 'est_correct')


class QuestionDeQuizInline(admin.TabularInline):
    model = QuestionDeQuiz
    extra = 1
    fields = ('order', 'enonce', 'type_de_question', 'explication')
    show_change_link = True


@admin.register(Competence)
class CompetenceAdmin(admin.ModelAdmin):
    list_display = ('code', 'libelle', 'company', 'validite_mois', 'active')
    list_filter = ('company', 'active')
    search_fields = ('code', 'libelle', 'description')


@admin.register(Quiz)
class QuizAdmin(admin.ModelAdmin):
    list_display = ('titre', 'course', 'note_minimale', 'tentatives_max',
                    'nombre_de_questions')
    list_filter = ('course__company',)
    search_fields = ('titre', 'course__title')
    inlines = [QuestionDeQuizInline]


@admin.register(QuestionDeQuiz)
class QuestionDeQuizAdmin(admin.ModelAdmin):
    """Les choix se saisissent ICI, et non dans la page du quiz.

    Un inline dans un inline n'existe pas dans l'admin Django : les
    questions se créent depuis le quiz, puis chacune s'ouvre pour recevoir
    ses choix. Le lien « Modifier » de la ligne de question y mène.
    """
    list_display = ('enonce_court', 'quiz', 'type_de_question', 'order',
                    'nombre_de_bonnes_reponses')
    list_filter = ('type_de_question', 'quiz__course__company')
    search_fields = ('enonce',)
    inlines = [ChoixDeQuestionInline]

    @admin.display(description='Énoncé')
    def enonce_court(self, obj):
        return obj.enonce[:70]

    @admin.display(description='Bonnes réponses')
    def nombre_de_bonnes_reponses(self, obj):
        """Zéro bonne réponse est une erreur de saisie, et elle se voit ici.

        Le moteur compte une telle question FAUSSE pour tout le monde — la
        compter juste offrirait des points gratuits et masquerait l'oubli.
        """
        nombre = len(obj.choix_corrects)
        return nombre if nombre else '⚠ aucune'


@admin.register(TentativeDeQuiz)
class TentativeDeQuizAdmin(admin.ModelAdmin):
    list_display = ('user', 'quiz', 'numero', 'score',
                    'note_minimale_appliquee', 'reussie', 'finie_le')
    list_filter = ('reussie', 'quiz__course__company')
    search_fields = ('user__username', 'quiz__titre')
    # Un résultat ne se retouche pas à la main : il se repasse.
    readonly_fields = ('quiz', 'user', 'numero', 'debutee_le', 'finie_le',
                       'score', 'reussie', 'note_minimale_appliquee')


@admin.register(ValidationTerrain)
class ValidationTerrainAdmin(admin.ModelAdmin):
    """Consultation et correction d'écriture.

    Prononcer une validation se fait sur l'écran du valideur
    (/erp/formations/competences/validations/), qui applique la règle « un
    apprenant ne valide pas sa propre compétence ». L'admin ne la rejoue
    pas : il sert à relire et à corriger une saisie, sous le contrôle des
    droits Django et du journal d'audit.
    """
    list_display = ('apprenant', 'competence', 'statut', 'constatee_le',
                    'lieu', 'valide_par', 'expire_le')
    list_filter = ('statut', 'competence__company')
    search_fields = ('apprenant__username', 'competence__code', 'lieu')
    autocomplete_fields = ()
    readonly_fields = ('demandee_le',)
