"""
apps/btp/guided_quote_pdf.py — Génération du PDF de pré-devis pour une
GuidedQuoteRequest. Pattern repris de
apps/competitor_intelligence/services/report_service.py (reportlab, déjà
utilisé et fonctionnel dans le repo — aucune nouvelle dépendance).
"""
import io


def generate_guided_quote_pdf(quote_request, public_url=''):
    """Génère le PDF de pré-devis (infos client, prestations, estimation,
    conditions, QR code, signature électronique simplifiée)."""
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import cm
        from reportlab.lib import colors
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
    except ImportError:
        raise ImportError('reportlab requis : pip install reportlab')

    from django.utils import timezone

    estimate = getattr(quote_request, 'estimate', None)
    company = quote_request.company

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=2 * cm, rightMargin=2 * cm,
                             topMargin=1.5 * cm, bottomMargin=1.5 * cm)
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('TitleElec', parent=styles['Title'], textColor=colors.HexColor('#0F172A'))
    story = []

    story.append(Paragraph(f'Pré-devis {quote_request.reference}', title_style))
    story.append(Paragraph(f'{company.name} — {timezone.now().strftime("%d/%m/%Y")}', styles['Normal']))
    story.append(Spacer(1, 0.5 * cm))

    # ─── Informations client ────────────────────────────────────────────────────
    story.append(Paragraph('Client', styles['Heading2']))
    client_rows = [
        ['Nom', quote_request.client_full_name],
        ['Email', quote_request.client_email],
        ['Téléphone', quote_request.client_phone or '—'],
        ['Adresse', f'{quote_request.address}, {quote_request.zip_code} {quote_request.city}'.strip(', ')],
        ['Type de demande', quote_request.get_request_type_display()],
        ['Niveau de gamme', quote_request.get_quality_level_display()],
    ]
    t = Table(client_rows, colWidths=[4 * cm, 12 * cm])
    t.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LINEBELOW', (0, 0), (-1, -1), 0.25, colors.HexColor('#E5E7EB')),
    ]))
    story.append(t)
    story.append(Spacer(1, 0.5 * cm))

    # ─── Résumé / prestations ───────────────────────────────────────────────────
    story.append(Paragraph('Résumé des prestations estimées', styles['Heading2']))
    if estimate:
        rows = [['Prestation', 'Qté', 'Unité', 'PU moyen HT', 'Total HT']]
        for item in estimate.items.all().order_by('order'):
            rows.append([
                item.description, str(item.quantity), item.unit,
                f'{item.unit_price_avg:.2f} €', f'{item.total_avg:.2f} €',
            ])
        t = Table(rows, colWidths=[7 * cm, 1.8 * cm, 2 * cm, 3 * cm, 3 * cm])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0F172A')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 8.5),
            ('GRID', (0, 0), (-1, -1), 0.25, colors.HexColor('#E5E7EB')),
            ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
        ]))
        story.append(t)
        story.append(Spacer(1, 0.4 * cm))

        totals = [
            ['Main d\'œuvre HT', f'{estimate.labor_amount:.2f} €'],
            ['Matériel HT', f'{estimate.materials_amount:.2f} €'],
            ['Déplacement', f'{estimate.travel_amount:.2f} €'],
            ['Majoration urgence', f'{estimate.urgency_surcharge:.2f} €'],
            ['Fourchette estimée HT', f'{estimate.amount_min_ht:.2f} € — {estimate.amount_max_ht:.2f} €'],
            ['Total moyen TTC (indicatif)', f'{estimate.total_ttc:.2f} €'],
        ]
        t2 = Table(totals, colWidths=[8 * cm, 4 * cm])
        t2.setStyle(TableStyle([
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
            ('LINEABOVE', (0, -1), (-1, -1), 0.5, colors.HexColor('#0F172A')),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ]))
        story.append(t2)
        story.append(Spacer(1, 0.3 * cm))
        story.append(Paragraph(estimate.disclaimer or
                                'Estimation indicative sans engagement, établie à distance sur la base des '
                                'informations fournies. Un devis ferme sera établi après visite technique.',
                                styles['Italic']))
    else:
        story.append(Paragraph('Estimation en cours d\'analyse par nos équipes.', styles['Normal']))

    story.append(Spacer(1, 0.6 * cm))

    # ─── QR code (suivi en ligne) ───────────────────────────────────────────────
    if public_url:
        qr_img = _make_qr_image(public_url)
        if qr_img:
            story.append(Paragraph('Suivre votre demande en ligne :', styles['Normal']))
            story.append(Image(qr_img, width=2.5 * cm, height=2.5 * cm))
            story.append(Spacer(1, 0.4 * cm))

    # ─── Signature électronique (simplifiée) ───────────────────────────────────
    story.append(Paragraph('Acceptation', styles['Heading2']))
    story.append(Paragraph(
        'Ce pré-devis est une estimation. L\'acceptation définitive et la signature électronique '
        'se font en ligne via le lien de suivi ci-dessus.', styles['Normal']))

    doc.build(story)
    buf.seek(0)
    return buf


def _make_qr_image(data):
    try:
        import qrcode
    except ImportError:
        return None
    qr = qrcode.QRCode(version=None, error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=8, border=2)
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color='#0F172A', back_color='white')
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    buf.seek(0)
    return buf
