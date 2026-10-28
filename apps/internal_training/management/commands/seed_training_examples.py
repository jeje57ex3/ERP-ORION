"""
Management command — Crée des formations d'exemple pour une entreprise.

Usage :
  python manage.py seed_training_examples
  python manage.py seed_training_examples --company-id 1
"""
from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth.models import User


class Command(BaseCommand):
    help = 'Crée des formations d\'exemple pour l\'entreprise cible'

    def add_arguments(self, parser):
        parser.add_argument(
            '--company-id', type=int, default=None,
            help='ID de l\'entreprise cible (première entreprise par défaut)',
        )
        parser.add_argument(
            '--force', action='store_true',
            help='Recrée les formations même si elles existent déjà',
        )

    def handle(self, *args, **options):
        from apps.core.models import Company
        from apps.internal_training.services import (
            create_course, publish_course,
            create_chapter, create_page, add_block,
        )
        from apps.internal_training.models import TrainingCourse

        company_id = options['company_id']
        if company_id:
            try:
                company = Company.objects.get(pk=company_id)
            except Company.DoesNotExist:
                raise CommandError(f'Entreprise #{company_id} introuvable.')
        else:
            company = Company.objects.filter(is_active=True).first()
            if not company:
                raise CommandError('Aucune entreprise active trouvée.')

        admin_user = User.objects.filter(is_superuser=True).first()

        self.stdout.write(f'Entreprise : {company.name}')

        COURSES = [
            {
                'title': 'Accueil & Onboarding Orion',
                'description': 'Formation d\'accueil pour les nouveaux collaborateurs. Découvrez l\'ERP, les outils et la culture de l\'entreprise.',
                'chapters': [
                    {
                        'title': 'Bienvenue dans l\'équipe',
                        'pages': [
                            {
                                'title': 'Présentation de l\'entreprise',
                                'blocks': [
                                    {'type': 'text', 'content': 'Bienvenue ! Cette formation vous guidera dans vos premiers jours avec nous.'},
                                    {'type': 'annotation', 'content': 'Conseil : prenez le temps de lire chaque section avant de passer à la suivante.'},
                                ],
                            },
                            {
                                'title': 'Valeurs & Culture',
                                'blocks': [
                                    {'type': 'text', 'content': 'Nos valeurs fondamentales : excellence, intégrité, innovation et collaboration.'},
                                ],
                            },
                        ],
                    },
                    {
                        'title': 'Prise en main d\'Orion ERP',
                        'pages': [
                            {
                                'title': 'Interface et navigation',
                                'blocks': [
                                    {'type': 'text', 'content': 'Orion ERP est accessible depuis votre navigateur. La barre latérale gauche contient tous les modules activés pour votre entreprise.'},
                                    {'type': 'annotation', 'content': 'Utilisez le sélecteur d\'entreprise en haut pour basculer entre vos espaces.'},
                                ],
                            },
                        ],
                    },
                ],
            },
            {
                'title': 'Sécurité informatique — Bases',
                'description': 'Les fondamentaux de la cybersécurité pour protéger les données de l\'entreprise.',
                'chapters': [
                    {
                        'title': 'Mots de passe & Authentification',
                        'pages': [
                            {
                                'title': 'Créer un mot de passe fort',
                                'blocks': [
                                    {'type': 'text', 'content': 'Un mot de passe fort contient au minimum 12 caractères, avec des majuscules, minuscules, chiffres et symboles.'},
                                    {'type': 'annotation', 'content': 'Ne réutilisez jamais le même mot de passe sur plusieurs services.'},
                                ],
                            },
                            {
                                'title': 'Authentification à deux facteurs',
                                'blocks': [
                                    {'type': 'text', 'content': 'L\'authentification à deux facteurs (2FA) ajoute une couche de sécurité supplémentaire. Activez-la sur tous vos comptes professionnels.'},
                                ],
                            },
                        ],
                    },
                    {
                        'title': 'Phishing & Arnaques',
                        'pages': [
                            {
                                'title': 'Reconnaître un email frauduleux',
                                'blocks': [
                                    {'type': 'text', 'content': 'Les emails de phishing imitent des expéditeurs légitimes. Vérifiez toujours l\'adresse réelle de l\'expéditeur.'},
                                    {'type': 'annotation', 'content': 'En cas de doute, ne cliquez jamais sur les liens et contactez votre responsable informatique.'},
                                ],
                            },
                        ],
                    },
                ],
            },
        ]

        created = 0
        for course_data in COURSES:
            existing = TrainingCourse.objects.filter(
                company=company, title=course_data['title'],
            ).first()
            if existing and not options['force']:
                self.stdout.write(f'  ↳ Existe déjà : {course_data["title"]}')
                continue
            if existing and options['force']:
                existing.delete()

            course = create_course(
                company=company,
                title=course_data['title'],
                description=course_data.get('description', ''),
                created_by=admin_user,
            )

            for chapter_data in course_data.get('chapters', []):
                chapter = create_chapter(course=course, title=chapter_data['title'])
                for page_data in chapter_data.get('pages', []):
                    page = create_page(chapter=chapter, title=page_data['title'])
                    for block_data in page_data.get('blocks', []):
                        add_block(
                            page=page,
                            block_type=block_data['type'],
                            content=block_data.get('content', ''),
                        )
                    page.status = 'published'
                    page.save(update_fields=['status'])

            publish_course(course)
            self.stdout.write(self.style.SUCCESS(f'  ✓ {course.title}'))
            created += 1

        self.stdout.write(self.style.SUCCESS(f'\n{created} formation(s) créée(s) pour {company.name}.'))
