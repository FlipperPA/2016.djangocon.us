import os
import tablib
import unicodecsv

from django.contrib.auth.decorators import user_passes_test
from django.contrib.sites.models import Site
from django.contrib.sites.shortcuts import get_current_site
from django.core.urlresolvers import reverse, reverse_lazy
from django.http import HttpResponse
from django.shortcuts import render
from django.utils.text import slugify
from symposion.proposals.models import ProposalBase
from symposion.reviews.models import ProposalResult
from symposion.schedule.models import Slot
from symposion.speakers.models import Speaker
from symposion.sponsorship.models import Sponsor
from unidecode import unidecode


# TODO: This should be stored in settings or the DB. This will do for now.
SPONSOR_PLANS = {
    'diamond': 8,
    'platinum': 8,
    'gold': 4,
    'silver': 2,
    'bronze': 1,
}


def get_access_code(sponsor):
    """Given a sponsor we'll create an access code."""

    # Set this environment variable to format the access code
    ticket_hash_code = os.environ.get('DJANGOCON_SPONSOR_HASH', '{sponsor_name}-{level_name}-{sponsor_id}')

    access_code = ticket_hash_code.format(
        sponsor_id=sponsor.id,
        sponsor_name=slugify(sponsor.name),
        level_name=slugify(sponsor.level.name)
    )
    return access_code


@user_passes_test(lambda user: user.is_superuser)
def data_home(request):
    return render(
        request,
        "data.html",
        {
            'downloadables': [
                {
                    'name': 'Export Proposals',
                    'url': reverse_lazy('proposal_export')
                },
                {
                    'name': 'Export Speakers',
                    'url': reverse_lazy('speaker_export')
                },
                {
                    'name': 'Guidebook: Schedule Export',
                    'url': reverse_lazy('schedule_guidebook')
                },
                {
                    'name': 'Guidebook: Speaker Export',
                    'url': reverse_lazy('guidebook_speaker_export')
                },
                {
                    'name': 'Guidebook: Sponsor Export',
                    'url': reverse_lazy('guidebook_sponsor_export')
                },
                {
                    'name': 'Mailchimp: Sponsor Export',
                    'url': reverse_lazy('mailchimp_sponsor_export')
                },
                {
                    'name': 'Mailchimp: Export Sponsors (Markdown/HTML)',
                    'url': reverse_lazy('sponsors_raw')
                },
                {
                    'name': 'Ticketbud: Sponsor Export',
                    'url': reverse_lazy('ticketbud_sponsor_export')
                },
            ]
        }
    )


@user_passes_test(lambda user: user.is_superuser)
def proposal_export(request):
    content_type = 'text/csv'
    response = HttpResponse(content_type=content_type)
    response['Content-Disposition'] = 'attachment; filename="proposal_export.csv"'

    domain = get_current_site(request).domain
    writer = unicodecsv.writer(response, quoting=unicodecsv.QUOTE_ALL)
    writer.writerow([
        'id',
        'proposal_type',
        'speaker',
        'speaker_email',
        'title',
        'audience_level',
        'kind',
        'recording_release',
        'status',
        'comment_count',
        'score',
        'plus_one',
        'plus_zero',
        'minus_zero',
        'minus_one',
        'review_detail',
    ])

    proposals = ProposalBase.objects.all().select_subclasses().order_by('id')
    for proposal in proposals:
        try:
            proposal.result
        except ProposalResult.DoesNotExist:
            ProposalResult.objects.get_or_create(proposal=proposal)

        writer.writerow([
            proposal.id,
            proposal.kind,
            proposal.speaker,
            proposal.speaker.email,
            proposal.title,
            proposal.get_audience_level_display(),
            proposal.kind,
            proposal.recording_release,
            proposal.status,
            proposal.result.comment_count,
            proposal.result.score,
            proposal.result.plus_one,
            proposal.result.plus_zero,
            proposal.result.minus_zero,
            proposal.result.minus_one,
            'https://{0}{1}'.format(domain, reverse('review_detail',
                                                    args=[proposal.pk])),
        ])
    return response


@user_passes_test(lambda user: user.is_superuser)
def speaker_export(request):
    content_type = 'text/csv'
    response = HttpResponse(content_type=content_type)
    response['Content-Disposition'] = 'attachment; filename="speaker_export.csv"'

    writer = unicodecsv.writer(response, quoting=unicodecsv.QUOTE_ALL)
    writer.writerow([
        'id',
        'name',
        'email'
    ])

    speakers = Speaker.objects.all().order_by('id')
    for speaker in speakers:
        writer.writerow([
            speaker.id,
            speaker.name,
            speaker.email,
        ])
    return response


@user_passes_test(lambda user: user.is_superuser)
def schedule_guidebook(request):
    headers = (
        'Session Title',
        'Date',
        'Time Start',
        'Time End',
        'Room/Location',
        'Schedule Track (Optional)',
        'Description (Optional)'
    )

    slots = Slot.objects.all().order_by('start')
    data = []
    for slot in slots:
        # authors = slot.content.speakers() if hasattr(slot.content, 'speakers') else []

        if slot.content_override:
            name = slot.content_override
        else:
            name = slot.content.title if hasattr(slot.content, 'title') else ''

        description = slot.content.description if hasattr(slot.content, 'description') else ''
        description = unidecode(description)
        description = description.replace('\r', '')
        description = description.replace('\n', '<br>')
        room_location = ', '.join(room['name'] for room in slot.rooms.values())
        track = slot.content.proposal.get_audience_level_display() if hasattr(slot.content, 'proposal') else ''

        if track == 'Not Applicable':
            track = 'N/A'

        slot_data = [
            name,
            slot.day.date.isoformat(),
            slot.start.isoformat(),
            slot.end.isoformat(),
            room_location,
            track,
            description,
        ]

        data.append(slot_data)

    data = tablib.Dataset(*data, headers=headers)

    response = HttpResponse(
        data.xlsx,
        content_type='application/vnd.ms-excel'
    )
    response['Content-Disposition'] = 'attachment; filename="guidebook_schedule.xls"'
    return response


@user_passes_test(lambda user: user.is_superuser)
def guidebook_sponsor_export(request):
    content_type = 'text/csv'
    response = HttpResponse(content_type=content_type)
    response['Content-Disposition'] = 'attachment; filename="guidebook_sponsors.csv"'

    writer = unicodecsv.writer(response, quoting=unicodecsv.QUOTE_ALL)
    writer.writerow([
        'Name',
        'Sub-Title (i.e. Location, Table/Booth, or Title/Sponsorship Level)',
        'Description (Optional)',
        'Location/Room',
        'Image (Optional)'
    ])

    sponsors = Sponsor.objects.filter(active=True).order_by("level")
    for sponsor in sponsors:
        writer.writerow([
            sponsor.name,
            sponsor.level.name,
            sponsor.listing_text,
            '',
            sponsor.website_logo.url
        ])

    return response


@user_passes_test(lambda user: user.is_superuser)
def mailchimp_sponsor_export(request):
    content_type = 'text/csv'
    response = HttpResponse(content_type=content_type)
    response['Content-Disposition'] = 'attachment; filename="mailchimp_sponsor.csv"'

    writer = unicodecsv.writer(response, quoting=unicodecsv.QUOTE_ALL)
    writer.writerow([
        'Email Address',
        'Company',
        'Sponsor Tier',
        'Full Name',
        'First Name',
        'Last Name',
        'Access Code',
    ])

    sponsors = Sponsor.objects.filter(active=True).order_by('level__order', 'name')
    for sponsor in sponsors:
        writer.writerow([
            sponsor.contact_email,
            sponsor.name,
            sponsor.level.name,
            sponsor.contact_name,
            sponsor.contact_name.split(' ')[0],
            sponsor.contact_name.split(' ')[-1],
            get_access_code(sponsor),
        ])

    return response


@user_passes_test(lambda user: user.is_superuser)
def ticketbud_sponsor_export(request):
    content_type = 'text/csv'
    response = HttpResponse(content_type=content_type)
    response['Content-Disposition'] = 'attachment; filename="ticketbud_sponsor.csv"'

    writer = unicodecsv.writer(response, quoting=unicodecsv.QUOTE_NONE)
    writer.writerow([
        'code',
        'price_off',
        'percent_off',
        'usage_limit',
        'start_time',
        'end_time',
        'times_used',
        'savings',
    ])

    sponsors = Sponsor.objects.filter(active=True).order_by('level__order', 'name')

    for sponsor in sponsors:
        writer.writerow([
            get_access_code(sponsor),
            0,
            0,
            SPONSOR_PLANS.get(sponsor.level.name.lower(), 0),
            None,
            None,
            None,
            0
        ])

    return response


@user_passes_test(lambda user: user.is_superuser)
def guidebook_speaker_export(request):
    content_type = 'text/csv'
    response = HttpResponse(content_type=content_type)
    response['Content-Disposition'] = 'attachment; filename="guidebook_speakers.csv"'

    writer = unicodecsv.writer(response, quoting=unicodecsv.QUOTE_ALL)
    writer.writerow([
        'Name',
        'Sub-Title (i.e. Location, Table/Booth, or Title/Sponsorship Level)',
        'Description (Optional)',
        'Location/Room',
        'Image (Optional)'
    ])

    speakers = Speaker.objects.filter(
        presentations__isnull=False,
        presentations__cancelled=False)
    for speaker in speakers:

        if hasattr(speaker.photo, 'url'):
            photo_url = speaker.photo.url
        else:
            photo_url = ''

        writer.writerow([
            speaker.name,
            '',
            unidecode(speaker.biography),
            '',
            photo_url,
        ])

    return response
