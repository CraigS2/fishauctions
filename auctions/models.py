import decimal
from django.utils import timezone, dateformat, html
import datetime
from django.contrib.auth.models import *
from django.db import models
from django.core.validators import *
from django.db.models import Count, Sum, Q, F
from django.db.models.expressions import RawSQL
from autoslug import AutoSlugField
from django.urls import reverse
from markdownfield.models import MarkdownField, RenderedMarkdownField
from markdownfield.validators import VALIDATOR_STANDARD
from easy_thumbnails.fields import ThumbnailerImageField
from location_field.models.plain import PlainLocationField
from django.db.models.signals import pre_save
from django.dispatch import receiver
import uuid
from random import randint
from django.conf import settings
from django.utils.formats import date_format
from django.contrib.sites.models import Site
import re
from django.contrib.auth.signals import user_logged_in
from dal import autocomplete
from pytz import timezone as pytz_timezone

def nearby_auctions(latitude, longitude, distance=100, include_already_joined=False, user=None, return_slugs=False):
	"""Return a list of auctions or auction slugs that are within a specified distance of the given location"""
	auctions = []
	slugs = []
	distances = []
	locations = PickupLocation.objects.annotate(distance=distance_to(latitude, longitude))\
		.exclude(distance__gt=distance)\
		.filter(auction__date_end__gte=timezone.now(), auction__date_start__lte=timezone.now())\
		.exclude(auction__promote_this_auction=False)\
		.exclude(auction__isnull=True)
	if user:
		if user.is_authenticated and not include_already_joined:
			locations = locations.exclude(auction__auctiontos__user=user)
		locations = locations.exclude(auction__auctionignore__user=user)	
	elif user and not include_already_joined:
		locations = locations.exclude(auction__auctiontos__user=user)
	for location in locations:
		if location.auction.slug not in slugs:
			auctions.append(location.auction)
			slugs.append(location.auction.slug)
			distances.append(location.distance)
	if return_slugs:
		return slugs
	else:
		return auctions, distances

def median_value(queryset, term):
    count = queryset.count()
    return queryset.values_list(term, flat=True).order_by(term)[int(round(count/2))]

def distance_to(latitude, longitude, unit='miles', lat_field_name="latitude", lng_field_name="longitude", approximate_distance_to=10):
	"""
	GeoDjango has been fustrating with MySQL and Point objects.
	This function is a workaound done using raw SQL.

	Given a latitude and longitude, it will return raw SQL that can be used to annotate a queryset

	The model being annotated must have fields named 'latitude' and 'longitude' for this to work

	For example:

	qs = model.objects.all()\
			.annotate(distance=distance_to(latitude, longitude))\
			.order_by('distance')
	"""
	if unit == "miles":
		correction = 0.6213712 # close enough
	else:
		correction = 1 # km
	for i in [latitude, longitude, lat_field_name, lng_field_name, approximate_distance_to]:
		if '"' in str(i) or "'" in str(i):
			raise TypeError("invalid character passed to distance_to, possible sql injection risk")
	# Great circle distance formula, CEILING is used to keep people from triangulating locations
	gcd_formula = f"CEILING( 6371 * acos(least(greatest( \
		cos(radians({latitude})) * cos(radians({lat_field_name})) \
		* cos(radians({lng_field_name}) - radians({longitude})) + \
		sin(radians({latitude})) * sin(radians({lat_field_name})) \
		, -1), 1)) * {correction} / {approximate_distance_to}) * {approximate_distance_to}"
	distance_raw_sql = RawSQL(
		gcd_formula, ()
	)
	# This one works fine when I print qs.query and run the output in SQL but does not work when Django runs the qs
	# Seems to be an issue with annotating on related entities
	# Injection attacks don't seem possible here because latitude and longitude can only contain a float as set in update_user_location()
	# gcd_formula = f"CEILING( 6371 * acos(least(greatest( \
	#     cos(radians(%s)) * cos(radians({lat_field_name})) \
	#     * cos(radians({lng_field_name}) - radians(%s)) + \
	#     sin(radians(%s)) * sin(radians({lat_field_name})) \
	#     , -1), 1)) * %s / {approximate_distance_to}) * {approximate_distance_to}"
	# distance_raw_sql = RawSQL(
	#     gcd_formula,
	#     (latitude, longitude, latitude, correction)
	# )
	return distance_raw_sql

def guess_category(text):
	"""Given some text, look up lots with similar names and make a guess at the category this `text` belongs to based on the category used there"""
	keywords = []
	words = re.findall('[A-Z|a-z]{3,}', text.lower())
	for word in words:
		if word not in settings.IGNORE_WORDS:
			keywords.append(word)

	if not keywords:
		return None
	lot_qs = Lot.objects.exclude(is_deleted=True).filter(category_automatically_added=False, species_category__isnull=False, is_deleted=False).exclude(species_category__pk=21).exclude(auction__promote_this_auction=False)
	q_objects = Q()
	for keyword in keywords:
		q_objects |= Q(lot_name__iregex=r'\b{}\b'.format(re.escape(keyword)))

	lot_qs = lot_qs.filter(q_objects)

	#category = lot_qs.values('species_category').annotate(count=Count('species_category')).order_by('-count').first()
	# attempting this as a single-shot query is extremely difficult to debug
	categories = {}
	for lot in lot_qs:
		if lot.species_category.pk == 21:
			print("lot!")
		matches = 0
		for keyword in keywords:
			if keyword in lot.lot_name.lower():
				matches += 1
		category_total = categories.get(lot.species_category.pk, 0)
		categories[lot.species_category.pk] = category_total + matches
	sorted_categories = sorted(categories.items(), key=lambda x: x[1], reverse=True)	
	for key, value in sorted_categories:
		#print(Category.objects.filter(pk=key).first(), value)
		return Category.objects.filter(pk=key).first()
	return None

class BlogPost(models.Model):
	"""
	A simple markdown blog.  At the moment, I don't feel that adding a full CMS is necessary
	"""
	title = models.CharField(max_length=255)
	slug = AutoSlugField(populate_from='title', unique=True)
	body = MarkdownField(rendered_field='body_rendered', validator=VALIDATOR_STANDARD, blank=True, null=True)
	body_rendered = RenderedMarkdownField(blank=True, null=True)
	date_posted = models.DateTimeField(auto_now_add=True)
	extra_js = models.TextField(max_length=16000, null=True, blank=True)

	def __str__(self):
		return self.title

class Location(models.Model):
	"""
	Allows users to specify a region -- USA, Canada, South America, etc.
	"""
	name = models.CharField(max_length=255)
	def __str__(self):
		return str(self.name)

class GeneralInterest(models.Model):
	"""Clubs and products belong to a general interest"""
	name = models.CharField(max_length=255)
	def __str__(self):
		return str(self.name)

class Club(models.Model):
	"""Users can self-select which club they belong to"""
	name = models.CharField(max_length=255)
	abbreviation = models.CharField(max_length=255, blank=True, null=True)
	homepage = models.CharField(max_length=255, blank=True, null=True)
	facebook_page = models.CharField(max_length=255, blank=True, null=True)
	contact_email = models.CharField(max_length=255, blank=True, null=True)
	date_contacted = models.DateTimeField(blank=True, null=True)
	notes = models.CharField(max_length=300, blank=True, null=True)
	notes.help_text = "Only visible in the admin site, never made public"
	interests = models.ManyToManyField(GeneralInterest, blank=True)
	active = models.BooleanField(default=True)
	latitude = models.FloatField(blank=True, null=True)
	longitude = models.FloatField(blank=True, null=True)
	location = models.CharField(max_length=500, blank=True, null=True)
	location.help_text = "Search Google maps with this address"
	location_coordinates = PlainLocationField(based_fields=['location'], blank=True, null=True, verbose_name="Map")

	class Meta:
		ordering = ['name']

	def __str__(self):
		return str(self.name)

class Category(models.Model):
	"""Picklist of species.  Used for product, lot, and interest"""
	name = models.CharField(max_length=255)
	def __str__(self):
		return str(self.name)
	class Meta:
		verbose_name_plural = "Categories"
		ordering = ['name']
		
class Product(models.Model):
	"""A species or item in the auction"""
	common_name = models.CharField(max_length=255)
	common_name.help_text = "The name usually used to describe this species"
	scientific_name = models.CharField(max_length=255, blank=True)
	scientific_name.help_text = "Latin name used to describe this species"
	breeder_points = models.BooleanField(default=True)
	category = models.ForeignKey(Category, null=True, on_delete=models.SET_NULL)
	def __str__(self):
		return f"{self.common_name} ({self.scientific_name})"
	class Meta:
		verbose_name_plural = "Products and species"

class Auction(models.Model):
	"""An auction is a collection of lots"""
	title = models.CharField("Auction name", max_length=255, blank=False, null=False)
	title.help_text = "This is the name people will see when joining your auction"
	slug = AutoSlugField(populate_from='title', unique=True)
	is_online = models.BooleanField(default=True)
	is_online.help_text = "Is this is an online auction with in-person pickup at one or more locations?"
	sealed_bid = models.BooleanField(default=False)
	sealed_bid.help_text = "Users won't be able to see what the current bid is"
	lot_entry_fee = models.PositiveIntegerField(default=0, validators=[MinValueValidator(0), MaxValueValidator(10)])
	lot_entry_fee.help_text = "The amount the seller will be charged if a lot sells"
	unsold_lot_fee = models.PositiveIntegerField(default=0, validators=[MinValueValidator(0), MaxValueValidator(10)])
	unsold_lot_fee.help_text = "The amount the seller will be charged if their lot doesn't sell"
	winning_bid_percent_to_club = models.PositiveIntegerField(default=0, validators=[MinValueValidator(0), MaxValueValidator(100)])
	winning_bid_percent_to_club.help_text = "In addition to the Lot entry fee, this percent of the winning price will be taken by the club"
	pre_register_lot_discount_percent = models.PositiveIntegerField(default=0, validators=[MinValueValidator(0), MaxValueValidator(100)])
	pre_register_lot_discount_percent.help_text = "Decrease the club cut if users add lots through this website"
	pre_register_lot_entry_fee_discount = models.PositiveIntegerField(default=0, validators=[MinValueValidator(0), MaxValueValidator(10)])
	pre_register_lot_entry_fee_discount.help_text = "Decrease the lot entry fee by this amount if users add lots through this website"
	date_posted = models.DateTimeField(auto_now_add=True)
	date_start = models.DateTimeField("Auction start date")
	date_start.help_text = "Bidding starts on this date"
	lot_submission_start_date = models.DateTimeField("Lot submission opens", null=True, blank=True)
	lot_submission_start_date.help_text = "Users can submit (but not bid on) lots on this date"
	lot_submission_end_date = models.DateTimeField("Lot submission ends", null=True, blank=True)
	date_end = models.DateTimeField("Bidding end date", blank=True, null=True)
	date_end.help_text = "Bidding will end on this date.  If last-minute bids are placed, bidding can go up to 1 hour past this time on those lots.  Note: This will not change the end date of existing lots."
	watch_warning_email_sent = models.BooleanField(default=False)
	invoiced = models.BooleanField(default=False)
	created_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL)
	location = models.CharField(max_length=300, null=True, blank=True)
	location.help_text = "State or region of this auction"
	notes = MarkdownField(rendered_field='notes_rendered', validator=VALIDATOR_STANDARD, blank=True, null=True, verbose_name="Rules", default="")
	notes.help_text = "To add a link: [Link text](https://www.google.com)"
	notes_rendered = RenderedMarkdownField(blank=True, null=True)
	code_to_add_lots = models.CharField(max_length=255, blank=True, null=True)
	code_to_add_lots.help_text = "This is like a password: People in your club will enter this code to put their lots in this auction"
	lot_promotion_cost = models.PositiveIntegerField(default=1, validators=[MinValueValidator(1)])
	first_bid_payout = models.PositiveIntegerField(default=0, validators=[MinValueValidator(0)])
	first_bid_payout.help_text = "This is a feature to encourage bidding.  Give each bidder this amount, for free.  <a href='/blog/encouraging-participation/' target='_blank'>More information</a>"
	promote_this_auction = models.BooleanField(default=True)
	promote_this_auction.help_text = "Show this to everyone in the list of auctions. <span class='text-warning'>Uncheck if this is a test or private auction</span>."
	is_chat_allowed = models.BooleanField(default=True)
	max_lots_per_user = models.PositiveIntegerField(null=True, blank=True)
	max_lots_per_user.help_text = "A user won't be able to add more than this many lots to this auction"
	allow_additional_lots_as_donation = models.BooleanField(default=True)
	allow_additional_lots_as_donation.help_text = "If you don't set max lots per user, this has no effect"
	email_first_sent = models.BooleanField(default=False)
	email_second_sent = models.BooleanField(default=False)
	email_third_sent = models.BooleanField(default=False)
	email_fourth_sent = models.BooleanField(default=False)
	email_fifth_sent = models.BooleanField(default=False)
	make_stats_public = models.BooleanField(default=True)
	make_stats_public.help_text = "Allow any user who has a link to this auction's stats to see them.  Uncheck to only allow the auction creator to view stats"
	bump_cost = models.PositiveIntegerField(blank=True, default=1, validators=[MinValueValidator(1)])
	bump_cost.help_text = "The amount a user will be charged each time they move a lot to the top of the list"
	use_categories = models.BooleanField(default=True, verbose_name="This is a fish auction")
	use_categories.help_text = "Check to use categories like Cichlids, Livebearers, etc."
	is_deleted = models.BooleanField(default=False)
	allow_bidding_on_lots = models.BooleanField(default=True)
	only_approved_sellers = models.BooleanField(default=False)
	only_approved_sellers.help_text = "Require admin approval before users can add lots.  This will not change permissions for users that have already joined."
	require_phone_number = models.BooleanField(default=False)
	require_phone_number.help_text = "Require users to have entered a phone number before they can join this auction"
	email_users_when_invoices_ready = models.BooleanField(default=True)
	invoice_payment_instructions = models.CharField(max_length=255, blank=True, null=True, default="")
	invoice_payment_instructions.help_text = "Shown to the user on their invoice.  For example, 'You will receive a seperate PayPal invoice with payment instructions'"
	# partial for #139
	minimum_bid = models.PositiveIntegerField(default=2, validators=[MinValueValidator(2)])
	minimum_bid.help_text = "Lowest price a lot can sell for."
	lot_entry_fee_for_club_members = models.PositiveIntegerField(default=0, validators=[MinValueValidator(0), MaxValueValidator(10)])
	lot_entry_fee_for_club_members.help_text = "Used instead of the standard entry fee, when you designate someone as a club member"
	winning_bid_percent_to_club_for_club_members = models.PositiveIntegerField(default=0, validators=[MinValueValidator(0), MaxValueValidator(100)])
	winning_bid_percent_to_club_for_club_members.help_text = "Used instead of the standard split, when you designate someone as a club member"
	SET_LOT_WINNER_URLS = (
		('', "Standard, bidder number/lot number only"),
		('presentation', 'Show a picture of the lot'),
		('autocomplete', 'Autocomplete, search by name or bidder number'),
	)
	set_lot_winners_url = models.CharField(
		max_length=20,
		choices=SET_LOT_WINNER_URLS,
		blank=True,
		default="presentation"
	)
	set_lot_winners_url.verbose_name = "Set lot winners"

	def __str__(self):
		result = self.title
		if "auction" not in self.title.lower():
			result += " auction"
		if not self.title.lower().startswith("the "):
			result = "The " + result
		return result
	
	def delete(self, *args, **kwargs):
		self.is_deleted=True
		self.save()	

	@property
	def location_qs(self):
		"""All locations associated with this auction"""
		return PickupLocation.objects.filter(auction=self.pk).order_by('name')

	@property
	def physical_location_qs(self):
		"""Find all non-default locations"""
		# I am not sure why we were excluding the default location, but it doesn't make sense to
		#return self.location_qs.exclude(Q(pickup_by_mail=True)|Q(is_default=True))
		return self.location_qs.exclude(pickup_by_mail=True)
	
	@property
	def location_with_location_qs(self):
		"""Find all locations that have coordinates - useful to see if there's an actual location associated with this auction.  By default, auctions get a location with no coordinates added"""
		return self.physical_location_qs.exclude(latitude=0,longitude=0)

	@property
	def number_of_locations(self):
		"""The number of physical locations this auction has"""
		return self.physical_location_qs.count()

	@property
	def all_location_count(self):
		"""All locations, even mail"""
		return self.location_qs.count()

	@property
	def auction_type(self):
		"""Returns whether this is an online, in-person, or hybrid auction for use in tooltips and templates.  See also auction_type_as_str for a friendly display version"""
		number_of_locations = self.number_of_locations
		if self.is_online and number_of_locations == 1:
			return "online_one_location"
		if self.is_online and number_of_locations > 1:
			return "online_multi_location"
		if self.is_online and number_of_locations == 0:
			return "online_no_location"
		if not self.is_online and number_of_locations == 1:
			return "inperson_one_location"
		if not self.is_online and number_of_locations > 1:
			return "inperson_multi_location"
		return "unknown"

	@property
	def auction_type_as_str(self):
		"""Returns friendly string of whether this is an online, in-person, or hybrid auction"""
		auction_type = self.auction_type
		if auction_type == "online_one_location":
			return "online auction with in-person pickup"
		if auction_type == "online_multi_location":
			return "online auction with in-person pickup at multiple locations"
		if auction_type == "online_no_location":
			return "online auction with no specified pickup location"
		if auction_type == "inperson_one_location":
			return "in-person auction"
		if auction_type == "inperson_multi_location":
			return "in person auction with lot delivery to additional locations"
		return "unknown auction type"							

	def get_absolute_url(self):
		return f'/auctions/{self.slug}/'

	def get_edit_url(self):
		return f'/auctions/{self.slug}/edit/'
	
	@property
	def label_print_link(self):
		return f"{self.get_absolute_url()}?printredirect={reverse('print_my_labels', kwargs={'slug': self.slug})}"

	@property
	def add_lot_link(self):
		return f'/lots/new/?auction={self.slug}'

	@property
	def view_lot_link(self):
		return f"/lots/?auction={self.slug}&status=all"

	@property
	def user_admin_link(self):
		return reverse("auction_tos_list", kwargs={'slug': self.slug}) 

	@property
	def set_lot_winners_link(self):
		return f"{self.get_absolute_url()}lots/set-winners/{self.set_lot_winners_url}"

	def permission_check(self, user):
		"""See if `user` can make changes to this auction"""
		if self.created_by == user:
			return True
		if user.is_superuser:
			return True
		if not user.is_authenticated:
			return False
		tos = AuctionTOS.objects.filter(is_admin=True, user=user, user__isnull=False, auction=self.pk).first()
		if tos:
			return True
		return False

	@property
	def pickup_locations_before_end(self):
		"""If there's a problem with the pickup location times, all of them need to be after the end date of the auction (or after the start date for an in-person auction).
		Returns the edit url for the first pickup location whose end time is before the auction end"""
		locations = self.location_qs
		time_to_use = self.date_end
		if not self.is_online:
			time_to_use = self.date_start
		for location in locations:
			error = False
			try:
				if location.pickup_time < time_to_use:
					error = True
				if location.second_pickup_time:
					if location.second_pickup_time < time_to_use:
						error = True
			except:
				error = False
			if error:
				return reverse("edit_pickup", kwargs={'pk': location.pk})
		return False
		
	@property
	def dynamic_end(self):
		"""The absolute latest a lot in this auction can end"""
		if self.sealed_bid:
			return self.date_end
		else:
			dynamic_end = datetime.timedelta(minutes=60)
			return self.date_end + dynamic_end

	@property
	def date_end_as_str(self):
		"""Human-reable end date of the auction; this will always be an empty string for in-person auctions"""
		if self.is_online:
			return self.date_end
		else:
			return ""

	@property
	def minutes_to_end(self):
		if not self.date_end:
			return 9999
		timedelta = self.date_end - timezone.now()
		seconds = timedelta.total_seconds()
		if seconds < 0:
			return 0
		minutes = seconds // 60
		return minutes

	@property
	def ending_soon(self):
		"""Used to send notifications"""
		if self.minutes_to_end < 120:
			return True
		else:
			return False
	
	@property
	def closed(self):
		"""For display on the main auctions list"""
		if self.is_online and self.date_end:
			if timezone.now() > self.dynamic_end:
				return True
		# in-person auctions don't end right now
		return False

	@property
	def started(self):
		"""For display on the main auctions list"""
		if timezone.now() > self.date_start:
			return True
		else:
			return False

	@property
	def club_profit_raw(self):
		"""Total amount made by the club in this auction.  This number does not take into account rounding in the invoices, nor any invoice adjustments"""
		allLots = Lot.objects.exclude(is_deleted=True).filter(auction=self.pk)
		total = 0
		for lot in allLots:
			total += lot.club_cut
		return total

	@property
	def club_profit(self):
		"""Total amount made by the club in this auction, including rounding in the customer's favor in invoices"""
		try:
			invoices = Invoice.objects.filter(auction=self.pk)
			total = 0
			for invoice in invoices:
				total -= invoice.calculated_total
			return total
		except:
			return 0

	@property
	def gross(self):
		"""Total value of all lots sold"""
		try:
			gross = Lot.objects.exclude(is_deleted=True).filter(auction=self.pk).aggregate(Sum('winning_price'))['winning_price__sum']
			if gross is None:
				gross = 0
			return gross
		except:
			return 0

	@property
	def total_to_sellers(self):
		"""Total amount paid out to all sellers"""
		return self.gross - self.club_profit

	@property
	def percent_to_club(self):
		"""Percent of gross that went to the club"""
		if self.gross:
			return self.club_profit/self.gross * 100
		else:
			return 0

	@property
	def invoice_recalculate(self):
		"""Force update of all invoice totals in this auction"""
		invoices = Invoice.objects.filter(auction=self.pk)
		for invoice in invoices:
			invoice.recalculate
			invoice.save()

	@property
	def number_of_confirmed_tos(self):
		"""How many people selected a pickup location in this auction"""
		return AuctionTOS.objects.filter(auction=self.pk).count()

	@property
	def number_of_sellers(self):
		return AuctionTOS.objects.filter(auctiontos_seller__auction=self.pk, auctiontos_winner__isnull=False).distinct().count()
		#users = User.objects.values('lot__user').annotate(Sum('lot')).filter(lot__auction=self.pk, lot__winner__isnull=False)
		#users = User.objects.filter(lot__auction=self.pk, lot__winner__isnull=False).distinct()

	# @property
	# def number_of_unsuccessful_sellers(self):
	#	"""This is the number of sellers who didn't sell ALL their lots"""
	# 	users = User.objects.values('lot__user').annotate(Sum('lot')).filter(lot__auction=self.pk, lot__winner__isnull=True)
	#   users = User.objects.filter(lot__auction=self.pk, lot__winner__isnull=True).distinct()
	# 	return len(users)

	@property
	def number_of_buyers(self):
		#users = User.objects.values('lot__winner').annotate(Sum('lot')).filter(lot__auction=self.pk)
		return AuctionTOS.objects.filter(auctiontos_winner__auction=self.pk).distinct().count()
		#users = User.objects.filter(winner__auction=self.pk).distinct()

	@property
	def median_lot_price(self):
		lots = self.lots_qs.filter(winning_price__isnull=False)
		if lots:
			return median_value(lots,'winning_price')
		else:
			return 0
	
	@property
	def lots_qs(self):
		"""All lots in this auction"""
		return Lot.objects.exclude(is_deleted=True).filter(auction=self.pk)
	
	@property
	def total_sold_lots(self):
		return self.lots_qs.filter(winning_price__isnull=False).exclude(banned=True).count()

	@property
	def total_unsold_lots(self):
		return self.lots_qs.filter(winning_price__isnull=True).exclude(banned=True).count()

	@property
	def total_lots(self):
		return self.lots_qs.exclude(banned=True).count()

	@property
	def percent_unsold_lots(self):
		try:
			return self.total_unsold_lots / self.total_lots * 100
		except:
			return 100
	
	@property
	def show_lot_link_on_auction_list(self):
		if timezone.now() > self.lot_submission_start_date:
			return True
		return False

	@property
	def can_submit_lots(self):
		if timezone.now() < self.lot_submission_start_date:
			return False
		if self.lot_submission_end_date:
			if self.lot_submission_end_date < timezone.now():
				return False
			else:
				return True
		if self.is_online:
			if self.date_end > timezone.now():
				return False
		return True
	
	@property
	def bin_size(self):
		"""Used for auction stats graph - on the lot sell price chart, this is the the size of each bin"""
		try:
			return int(self.median_lot_price/5)
		except:
			return 2

	@property
	def number_of_participants(self):
		"""
		Number of users who bought or sold at least one lot
		"""
		buyers = AuctionTOS.objects.filter(auctiontos_winner__auction=self.pk).distinct()
		sellers = AuctionTOS.objects.filter(auctiontos_seller__auction=self.pk, auctiontos_winner__isnull=False).exclude(id__in=buyers).distinct()
		#buyers = User.objects.filter(winner__auction=self.pk).distinct()
		#sellers = User.objects.filter(lot__auction=self.pk, lot__winner__isnull=False).exclude(id__in=buyers).distinct()
		return len(sellers) + len(buyers)

	@property
	def number_of_tos(self):
		"""This will return users, ignoring any auctiontos without a user set"""
		return AuctionTOS.objects.filter(auction=self.pk).count()
	
	@property
	def preregistered_users(self):
		return AuctionTOS.objects.filter(auction=self.pk, manually_added=False).count()

	@property
	def multi_location(self):
		"""
		True if there's more than one location at this auction
		"""
		locations = self.physical_location_qs.count()
		if locations > 1:
			return True
		return False

	@property
	def no_location(self):
		"""
		True if there's no pickup location at all for this auction -- pickup by mail excluded
		"""
		locations = self.location_with_location_qs.count()
		if not locations:
			return True
		return False
		
	@property
	def can_be_deleted(self):
		if self.total_lots:
			return False
		else:
			return True
	@property
	def paypal_invoices(self):
		# all drafts and ready:
		#return Invoice.objects.filter(auction=self).exclude(status="PAID")
		# only ready:
		return Invoice.objects.filter(auction=self, status="UNPAID")

	@property
	def draft_paypal_invoices(self):
		"""Used for a tooltip warning telling people to make invoices ready"""
		return Invoice.objects.filter(auction=self, status="DRAFT", calculated_total__lt=0).count()

	@property
	def paypal_invoice_chunks(self):
		"""
		Needed to know how many chunks to split the inovice list to
		https://www.paypal.com/invoice/batch
		used by views.auctionInvoicesPaypalCSV
		"""
		invoices = self.paypal_invoices
		chunks = 1
		count = 0
		chunkSize = 150
		returnList = [1]
		for invoice in invoices:
			if not invoice.user_should_be_paid: # only include users that need to pay us
				count += 1
				if count > chunkSize:
					chunks += 1
					returnList.append(chunks)
					count = 0
		return returnList

	@property
	def set_location_link(self):
		"""If there's a location without a lat and lng, this link will let you edit the first one found"""
		location = self.location_qs.filter(latitude=0,longitude=0, pickup_by_mail=False).first()
		if location:
			return f"/locations/edit/{location.pk}"
		return None

	@property
	def admin_checklist_completed(self):
		if self.admin_checklist_location_set and self.admin_checklist_rules_updated and self.admin_checklist_joined \
			and self.admin_checklist_others_joined and self.admin_checklist_lots_added and self.admin_checklist_winner_set \
			and self.admin_checklist_additional_admin:
			return True
		return False
	
	@property
	def admin_checklist_location_set(self):
		if not self.set_location_link:
			return True
		return False
	
	@property
	def admin_checklist_rules_updated(self):
		if "You should remove this line and edit this section to suit your auction." in self.notes:
			return False
		return True
	
	@property
	def admin_checklist_joined(self):
		if AuctionTOS.objects.filter(auction__pk=self.pk).filter(Q(user=self.created_by)|Q(is_admin=True)).count() > 0:
			return True
		return False
	
	@property
	def admin_checklist_others_joined(self):
		if self.number_of_tos > 1:
			return True
		return False

	@property
	def admin_checklist_lots_added(self):
		if self.lots_qs.count() > 0:
			return True
		return False

	@property
	def admin_checklist_winner_set(self):
		if self.is_online:
			return True
		if self.lots_qs.filter(auctiontos_winner__isnull=False).count():
			return True
		return False
	
	@property
	def admin_checklist_additional_admin(self):
		if self.is_online:
			return True
		if self.lots_qs.filter(auctiontos_winner__isnull=False).count():
			return True
		return False
	
class PickupLocation(models.Model):
	"""
	A pickup location associated with an auction
	A given auction can have multiple pickup locations
	"""
	name = models.CharField(max_length=50, default="", blank=True, null=True)
	name.help_text = "Location name shown to users.  e.x. University Mall in VT"
	user = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL)
	auction = models.ForeignKey(Auction, null=True, blank=True, on_delete=models.CASCADE)
	#auction.help_text = "If your auction isn't listed here, it may not exist or has already ended"
	description = models.CharField(max_length=300, blank=True, null=True)
	description.help_text = "Notes, shipping charges, etc.  For example: 'Parking lot near Sears entrance'"
	users_must_coordinate_pickup = models.BooleanField(default=False)
	users_must_coordinate_pickup.help_text = "You probably want this unchecked, to have everyone arrive at the same time."
	pickup_location_contact_name = models.CharField(max_length=200, blank=True, null=True, verbose_name="Contact person's name")
	pickup_location_contact_name.help_text = "Name of the person coordinating this pickup location.  Contact info is only shown to logged in users."
	pickup_location_contact_phone = models.CharField(max_length=200, blank=True, null=True, verbose_name="Contact person's phone")
	pickup_location_contact_email = models.CharField(max_length=200, blank=True, null=True, verbose_name="Contact person's email")
	pickup_time = models.DateTimeField(blank=True, null=True)
	second_pickup_time = models.DateTimeField(blank=True, null=True)
	second_pickup_time.help_text = "Only for <a href='/blog/multiple-location-auctions/'>multi-location auctions</a>; people will return to pick up lots from other locations at this time."
	latitude = models.FloatField(blank=True, default=0)
	longitude = models.FloatField(blank=True, default=0)
	address = models.CharField(max_length=500, blank=True, null=True)
	address.help_text = "Search Google maps with this address"
	location_coordinates = PlainLocationField(based_fields=['address'], blank=True, null=True, verbose_name="Map")
	allow_selling_by_default = models.BooleanField(default=True)
	allow_selling_by_default.help_text = "This is not used"
	allow_bidding_by_default = models.BooleanField(default=True)
	allow_bidding_by_default.help_text = "This is not used"
	pickup_by_mail = models.BooleanField(default=False)
	pickup_by_mail.help_text = "Special pickup location without an actual location"
	is_default = models.BooleanField(default=False)
	is_default.help_text = "This was a default location added for an in-person auction."
	contact_person = models.ForeignKey('AuctionTOS', null=True, blank=True, on_delete=models.SET_NULL)
	contact_person.help_text = "Only users that you have granted admin permissions to will show up here.  Their phone and email will be shown to users who select this location."

	def __str__(self):
		if self.pickup_by_mail:
			return "Mail me my lots"
		return self.name

	@property
	def short_name(self):
		if self.pickup_by_mail:
			return "Mail"
		words = self.name.split()
		abbreviation = ""
		for word in words:
			abbreviation += word[0].upper()
		return abbreviation

	@property
	def directions_link(self):
		"""Google maps link to the lat and lng of this pickup location"""
		if self.has_coordinates:
			return f"https://www.google.com/maps/search/?api=1&query={self.latitude},{self.longitude}"
		return ""

	@property
	def has_coordinates(self):
		"""Return True if this should be included on the auctions map list"""
		if self.latitude and self.longitude:
				return True
		return False

	@property
	def user_list(self):
		"""All auctiontos associated with this location"""
		return AuctionTOS.objects.filter(pickup_location=self.pk)

	@property
	def number_of_users(self):
		"""How many people have chosen this pickup location?"""
		return self.user_list.count()

	@property
	def incoming_lots(self):
		"""Queryset of all lots destined for this location"""
		return Lot.objects.filter(auctiontos_winner__pickup_location__pk=self.pk, is_deleted=False, banned=False)
	
	@property
	def outgoing_lots(self):
		"""Queryset of all lots coming from this location"""
		lots = Lot.objects.filter(auctiontos_seller__pickup_location__pk=self.pk, is_deleted=False, banned=False, auctiontos_winner__isnull=False)
		return lots
	
	@property
	def number_of_incoming_lots(self):
		return self.incoming_lots.count()
	
	@property
	def number_of_outgoing_lots(self):
		return self.outgoing_lots.count()
	
	@property
	def email_list(self):
		"""String of all email addresses associated with this location, used for bcc'ing all people at a location"""
		email = ""
		for user in self.user_list:
			if user.email:
				email += user.email + ", "
		return email

class AuctionIgnore(models.Model):
	"""If a user does not want to participate in an auction, create one of these"""
	user = models.ForeignKey(User, on_delete=models.CASCADE)
	auction = models.ForeignKey(Auction, on_delete=models.CASCADE)
	createdon = models.DateTimeField(auto_now_add=True, blank=True)
	def __str__(self):
		return f"{self.user} ignoring {self.auction}"
	class Meta: 
		verbose_name = "User ignoring auction"
		verbose_name_plural = "User ignoring auction"

class AuctionTOS(models.Model):
	"""Models how a user engages with an auction and is the basis for the user view when running an auction
	Usually this will correspond with a single person which may or may not also be a user"""
	user = models.ForeignKey(User, on_delete=models.SET_NULL, blank=True, null=True)
	auction = models.ForeignKey(Auction, on_delete=models.CASCADE)
	pickup_location = models.ForeignKey(PickupLocation, on_delete=models.CASCADE)
	createdon = models.DateTimeField(auto_now_add=True, blank=True)
	confirm_email_sent = models.BooleanField(default=False, blank=True)
	second_confirm_email_sent = models.BooleanField(default=False, blank=True)
	print_reminder_email_sent = models.BooleanField(default=False, blank=True)
	is_admin = 	models.BooleanField(default=False, verbose_name="Grant admin permissions to help run this auction", blank=True)
	# yes we are using a string to store a number
	# this is actually important because some day, someone will ask to make the bidder numbers have characters like "1-234" or people's names
	bidder_number = models.CharField(max_length=20, default="", blank=True)
	bidder_number.help_text = "Must be unique, blank to automatically generate"
	bidding_allowed = models.BooleanField(default=True, blank=True)
	selling_allowed = models.BooleanField(default=True, blank=True)
	name = models.CharField(max_length=181, null=True, blank=True)
	email = models.EmailField(null=True, blank=True)
	phone_number = models.CharField(max_length=20, blank=True, null=True)
	address = models.CharField(max_length=500, blank=True, null=True)
	manually_added = models.BooleanField(default=False, blank=True, null=True)
	time_spent_reading_rules = models.PositiveIntegerField(validators=[MinValueValidator(0)], blank=True, default=0)
	is_club_member = models.BooleanField(default=False, blank=True, verbose_name="Club member")

	@property
	def phone_as_string(self):
		"""Add proper dashes to phone"""
		if not self.phone_number:
			return ""
		n = re.sub('[^0-9]', "", self.phone_number)
		return format(int(n[:-1]), ",").replace(",", "-") + n[-1] 

	@property
	def bulk_add_link_html(self):
		"""Link to add multiple lots at once for this user"""
		url = reverse("bulk_add_lots", kwargs = {'bidder_number':self.bidder_number, 'slug':self.auction.slug})
		return html.format_html(f"<a href='{url}' hx-noget>Add lots</a>")

	@property
	def bought_lots_qs(self):
		lots = Lot.objects.exclude(is_deleted=True).filter(auctiontos_winner=self.pk)
		return lots

	@property
	def lots_qs(self):
		lots = Lot.objects.exclude(is_deleted=True).filter(auctiontos_seller=self.pk)
		return lots

	@property
	def unbanned_lot_qs(self):
		return self.lots_qs.exclude(banned=True)

	@property
	def unbanned_lot_count(self):
		return self.unbanned_lot_qs.count()

	@property
	def print_invoice_link_html(self):
		"""Link print lot labels for this user"""
		if self.unbanned_lot_count:
			url = reverse("print_labels_by_bidder_number", kwargs = {'bidder_number':self.bidder_number, 'slug':self.auction.slug})
			return html.format_html(f"<a href='{url}' hx-noget>Print labels</a>")
		return ""

	@property
	def invoice(self):
		return Invoice.objects.filter(auctiontos_user=self.pk).first()

	@property
	def invoice_link_html(self):
		"""HTML snippet with a link to the invoice for this auctionTOS, if set.  Otherwise, empty"""
		if self.invoice:
			result = html.format_html(f"<a href='{self.invoice.get_absolute_url()}' hx-noget>View</a>")
			return result
		else:
			return "None"

	def save(self, *args, **kwargs):
		if not self.pk:
			#print("new instance of auctionTOS")
			if self.auction.only_approved_sellers:
				self.selling_allowed = False
			# no emails for in-person auctions, thankyouverymuch
			if not self.auction.is_online:
				pass
				#self.confirm_email_sent = True
				#self.print_reminder_email_sent = True
				#self.second_confirm_email_sent = True
		# fill out some fields from user, if set
		# There is a huge security concern here:   <<<< ATTENTION!!!
		# If someone creates an auction and adds every email address that's public
		# We must avoid allowing them to collect addresses/phone numbers/locations from these people
		# Having this code below run only on creation means that the user won't be filled out and prevents collecting data
		# if making changes, remember that there's user_logged_in_callback below which sets the user field
		if self.user and not self.pk:
			if not self.name:
				self.name = self.user.first_name + " " + self.user.last_name
			if not self.email:
				self.email = self.user.email
			userData, created = UserData.objects.get_or_create(
				user = self.user,
				defaults={},
				)
			if not self.phone_number:
				self.phone_number = userData.phone_number
			if not self.address:
				self.address = userData.address
		# set the bidder number based on the phone, address, last used number, or just at random
		if not self.bidder_number or self.bidder_number == "None":
			dont_use_these = ['13', '14', '15', '16', '17', '18', '19']
			search = None
			if self.phone_number:
				search = re.search('([\d]{3}$)|$', self.phone_number).group()
			if not search or str(search) in dont_use_these:
				if self.address:
					search = re.search('([\d]{3}$)|$', self.address).group()
			if self.user:
				userData, created = UserData.objects.get_or_create(
					user = self.user,
					defaults={},
					)
				if userData.preferred_bidder_number:
					search = userData.preferred_bidder_number
			# I guess it's possible that someone could make 999 accounts and have them all join a single auction, which would turn this into an infinite loop
			failsafe = 0
			# bidder numbers shouldn't start with 0
			try:
				if str(search)[0] == "0":
					search = search[1:]
				if str(search)[0] == "0":
					search = search[1:]
			except:
				pass
			while failsafe < 6000:
				search = str(search)
				if search[:-2] not in dont_use_these and search != "None":
					if AuctionTOS.objects.filter(bidder_number=search, auction=self.auction).count() == 0:
						self.bidder_number = search
						if self.user:
							if not userData.preferred_bidder_number:
								userData.preferred_bidder_number = search
								userData.save()
						break
				# OK, give up and just randomly generate something
				search = randint(1, 999)
				failsafe += 1
		if not self.bidder_number:
			# I don't ever want this to be null
			self.bidder_number = 999
		super().save(*args, **kwargs) 

	@property
	def display_name_for_admins(self):
		"""Same as display name, but no anonymous option"""
		if self.auction.is_online:
			if self.user and not self.manually_added:
				return self.user.username
		if self.bidder_number:
			return self.bidder_number
		return "Unknown user"

	@property
	def display_name(self):
		"""Use usernames for online auctions, and bidder numbers for in-person auctions"""
		#return f"{self.user} will meet at {self.pickup_location} for {self.auction}"
		if self.auction.is_online:
			if self.user and not self.manually_added:
				userData, created = UserData.objects.get_or_create(
					user = self.user,
					defaults={},
				)
				if userData.username_visible:
					return self.user.username
				else:
					return "Anonymous"
		if self.bidder_number:
			return self.bidder_number
		return "Unknown user"

	def __str__(self):
		return self.display_name

	class Meta: 
		verbose_name = "User in auction"
		verbose_name_plural = "Users in auction"

	@property
	def closest_location_for_this_user(self):
		result = PickupLocation.objects.none()
		if self.user and self.auction.multi_location:
			userData, created = UserData.objects.get_or_create(
				user = self.user,
				defaults={},
			)
			if userData.latitude:
				result = PickupLocation.objects.filter(auction=self.auction)\
					.annotate(distance=distance_to(userData.latitude, userData.longitude))\
					.order_by('distance').first()
		return result

	@property
	def has_selected_closest_location(self):
		if self.closest_location_for_this_user:
			if self.closest_location_for_this_user == self.pickup_location:
				return True
			return False
		# single location auction, or user's location not set; anyway, not a problem
		return True
	
	@property
	def distance_traveled(self):
		if self.user and not self.manually_added:
			userData, created = UserData.objects.get_or_create(
				user = self.user,
				defaults={},
			)
			if userData.latitude:
				location = PickupLocation.objects.filter(pk=self.pickup_location.pk)\
							.annotate(distance=distance_to(userData.latitude, userData.longitude))\
							.order_by('distance').first()
				return location.distance
		return ""

	@property
	def closer_location_savings(self):
		if not self.has_selected_closest_location:
			if self.closest_location_for_this_user and self.distance_traveled:
				return int(self.distance_traveled - self.closest_location_for_this_user.distance)
		return 0

	@property
	def closer_location_warning(self):
		current_site = Site.objects.get_current()
		if self.closer_location_savings > 9:
			return f"You've selected {self.pickup_location}, but {self.closest_location_for_this_user} is {int(self.closer_location_savings)} miles closer to you.  You can change your pickup location on the auction rules page: https://{current_site.domain}{self.auction.get_absolute_url()}#join"
		return ""

	@property
	def closer_location_warning_html(self):
		current_site = Site.objects.get_current()
		if self.closer_location_savings > 9:
			return f"You've selected {self.pickup_location}, but {self.closest_location_for_this_user} is {int(self.closer_location_savings)} miles closer to you.  You can change your pickup location <a href='https://{current_site.domain}{self.auction.get_absolute_url()}#join'>on the auction rules page</a>"
		return ""

	@property
	def timezone(self):
		try:
			return pytz_timezone(self.user.userdata.timezone)
		except:
			try:
				return pytz_timezone(self.auction.created_by.userdata.timezone)
			except:
				return pytz_timezone(settings.TIME_ZONE)

	@property
	def pickup_time_as_localized_string(self):
		"""Do not use this in templates; it's for emails"""
		time = self.pickup_location.pickup_time
		localized_time = time.astimezone(self.timezone)
		return localized_time.strftime("%B %d at %I:%M %p")

	@property
	def second_pickup_time_as_localized_string(self):
		"""Do not use this in templates; it's for emails"""
		if self.pickup_location.second_pickup_time:
			time = self.pickup_location.second_pickup_time
			localized_time = time.astimezone(self.timezone)
			return localized_time.strftime("%B %d at %I:%M %p")
		return ""

	@property
	def auction_date_as_localized_string(self):
		"""Note that this is a different date for in person and online!"""
		if self.auction.is_online:
			time = self.auction.date_end
		else:
			# offline auctions use start time
			time = self.auction.date_start
		localized_time = time.astimezone(self.timezone)
		return localized_time.strftime("%B %d at %I:%M %p")

	@property
	def trying_to_avoid_ban(self):
		"""We track IPs in userdata, so we can do a quick check for this"""
		if self.user:
			userData, created = UserData.objects.get_or_create(
				user = self.user,
				defaults={},
			)
			if userData.last_ip_address:
				other_users = UserData.objects.filter(last_ip_address=userData.last_ip_address).exclude(pk=userData.pk)
				for other_user in other_users:
					#print(f"{self.user} is also known as {other_user.user}")
					banned = UserBan.objects.filter(banned_user=other_user.user, user=self.auction.created_by).first()
					if banned:
						url = reverse("userpage", kwargs={"slug": other_user.user.username})
						return f"<a href='{url}'>{other_user.user.username}</a>"
		return False

	@property
	def number_of_userbans(self):
		if self.user:
			other_bans = UserBan.objects.filter(banned_user=self.user)
			return other_bans.count()
		return ""

class Lot(models.Model):
	"""A lot is something to bid on"""
	PIC_CATEGORIES = (
		('ACTUAL', 'This picture is of the exact item'),
		('REPRESENTATIVE', "This is my picture, but it's not of this exact item.  e.x. This is the parents of these fry"),
		('RANDOM', 'This picture is from the internet'),
	)
	lot_number = models.AutoField(primary_key=True)
	custom_lot_number = models.CharField(max_length=9, blank=True, null=True)
	custom_lot_number.help_text = "You can override the default lot number with this"
	lot_name = models.CharField(max_length=40)
	slug = AutoSlugField(populate_from='lot_name', unique=False)
	lot_name.help_text = "Short description of this lot"
	image = ThumbnailerImageField(upload_to='images/', blank=True)
	image.help_text = "Optional.  Add a picture of the item here."
	image_source = models.CharField(
		max_length=20,
		choices=PIC_CATEGORIES,
		blank=True
	)
	image_source.help_text = "Where did you get this image?"
	i_bred_this_fish = models.BooleanField(default=False, verbose_name="I bred this fish/propagated this plant")
	i_bred_this_fish.help_text = "Check to get breeder points for this lot"
	description = MarkdownField(rendered_field='description_rendered', validator=VALIDATOR_STANDARD, blank=True, null=True)
	description.help_text = "To add a link: [Link text](https://www.google.com)"
	description_rendered = RenderedMarkdownField(blank=True, null=True)
	reference_link = models.URLField(blank=True, null=True)
	reference_link.help_text = "A URL with additional information about this lot"
	quantity = models.PositiveIntegerField(validators=[MinValueValidator(1)])
	quantity.help_text = "How many of this item are in this lot?"
	reserve_price = models.PositiveIntegerField(default=2, validators=[MinValueValidator(1), MaxValueValidator(2000)])
	reserve_price.help_text = "The minimum bid for this lot. Lot will not be sold unless someone bids at least this much"
	buy_now_price = models.PositiveIntegerField(default=None, validators=[MinValueValidator(1), MaxValueValidator(1000)], blank=True, null=True)
	buy_now_price.help_text = "This lot will be sold instantly for this price if someone is willing to pay this much.  Leave blank unless you know exactly what you're doing"
	species = models.ForeignKey(Product, null=True, blank=True, on_delete=models.SET_NULL)
	species_category = models.ForeignKey(Category, null=True, blank=True, on_delete=models.SET_NULL, verbose_name="Category")
	species_category.help_text = "An accurate category will help people find this lot more easily"
	date_posted = models.DateTimeField(auto_now_add=True, blank=True)
	last_bump_date = models.DateTimeField(null=True, blank=True)
	last_bump_date.help_text = "Any time a lot is bumped, this date gets changed.  It's used for sorting by newest lots."
	user = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL)
	auctiontos_seller = models.ForeignKey(AuctionTOS, null=True, blank=True, on_delete=models.SET_NULL, related_name="auctiontos_seller")
	auction = models.ForeignKey(Auction, blank=True, null=True, on_delete=models.SET_NULL)
	auction.help_text = "<span class='text-warning' id='last-auction-special'></span>Only auctions that you have <span class='text-warning'>selected a pickup location for</span> will be shown here. This lot must be brought to that location"
	date_end = models.DateTimeField(auto_now_add=False, blank=True, null=True)
	winner = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name="winner")
	auctiontos_winner = models.ForeignKey(AuctionTOS, null=True, blank=True, on_delete=models.SET_NULL, related_name="auctiontos_winner")
	active = models.BooleanField(default=True)
	winning_price = models.PositiveIntegerField(null=True, blank=True)
	refunded = models.BooleanField(default=False)
	refunded.help_text = "Don't charge the winner or pay the seller for this lot."
	banned = models.BooleanField(default=False, verbose_name="Removed")
	banned.help_text = "This lot will be hidden from views, and users won't be able to bid on it.  Removed lots are not charged in invoices."
	ban_reason = models.CharField(max_length=100, blank=True, null=True)
	deactivated = models.BooleanField(default=False)
	deactivated.help_text = "You can deactivate your own lots to remove all bids and stop bidding.  Lots can be reactivated at any time, but existing bids won't be kept"
	lot_run_duration = models.PositiveIntegerField(default=10, validators=[MinValueValidator(1), MaxValueValidator(30)])
	lot_run_duration.help_text = "Days to run this lot for"
	relist_if_sold = models.BooleanField(default=False)
	relist_if_sold.help_text = "When this lot sells, create a new copy of it.  Useful if you have many copies of something but only want to sell one at a time."
	relist_if_not_sold = models.BooleanField(default=False)
	relist_if_not_sold.help_text = "When this lot ends without being sold, reopen bidding on it.  Lots can be automatically relisted up to 5 times."
	relist_countdown = models.PositiveIntegerField(default=4, validators=[MinValueValidator(0), MaxValueValidator(10)])
	number_of_bumps = models.PositiveIntegerField(blank=True, default=0, validators=[MinValueValidator(0)])
	donation = models.BooleanField(default=False)
	donation.help_text = "All proceeds from this lot will go to the club"
	watch_warning_email_sent = models.BooleanField(default=False)
	# seller and buyer invoice are no longer needed and can safely be removed in a future migration
	seller_invoice = models.ForeignKey('Invoice', null=True, blank=True, on_delete=models.SET_NULL, related_name="seller_invoice")
	buyer_invoice = models.ForeignKey('Invoice', null=True, blank=True, on_delete=models.SET_NULL, related_name="buyer_invoice")
	transportable = models.BooleanField(default=True)
	promoted = models.BooleanField(default=False, verbose_name="Promote this lot")
	promoted.help_text = "This does nothing right now lol"
	promotion_budget = models.PositiveIntegerField(default=2, validators=[MinValueValidator(0), MaxValueValidator(5)])
	promotion_budget.help_text = "The most money you're willing to spend on ads for this lot."
	# promotion weight started out as a way to test how heavily a lot should get promoted, but it's now used as a random number generator
	# to allow some stuff that's not in your favorite cateogy to show up in the recommended list
	promotion_weight = models.PositiveIntegerField(default=0, validators=[MinValueValidator(0), MaxValueValidator(20)])
	feedback_rating = models.IntegerField(default = 0, validators=[MinValueValidator(-1), MaxValueValidator(1)])
	feedback_text = models.CharField(max_length=100, blank=True, null=True)
	winner_feedback_rating = models.IntegerField(default = 0, validators=[MinValueValidator(-1), MaxValueValidator(1)])
	winner_feedback_text = models.CharField(max_length=100, blank=True, null=True)
	date_of_last_user_edit = models.DateTimeField(auto_now_add=True, blank=True)
	is_chat_allowed = models.BooleanField(default=True)
	is_chat_allowed.help_text = "Uncheck to prevent chatting on this lot.  This will not remove any existing chat messages"
	buy_now_used = models.BooleanField(default=False)

	# Location, populated from userdata.  This is needed to prevent users from changing their address after posting a lot
	latitude = models.FloatField(blank=True, null=True)
	longitude = models.FloatField(blank=True, null=True)
	address = models.CharField(max_length=500, blank=True, null=True)
	
	# Payment and shipping options, populated from last submitted lot
	# Only show these fields if auction is set to none
	payment_paypal = models.BooleanField(default=False, verbose_name="Paypal accepted")
	payment_cash = models.BooleanField(default=False, verbose_name="Cash accepted")
	payment_other = models.BooleanField(default=False, verbose_name="Other payment method accepted")
	payment_other_method = models.CharField(max_length=80, blank=True, null=True, verbose_name="Payment method")
	payment_other_address = models.CharField(max_length=200, blank=True, null=True, verbose_name="Payment address")
	payment_other_address.help_text = "The address or username you wish to get payment at"
	# shipping options
	local_pickup = models.BooleanField(default=False)
	local_pickup.help_text = "Check if you'll meet people in person to exchange this lot"
	other_text = models.CharField(max_length=200, blank=True, null=True, verbose_name="Shipping notes")
	other_text.help_text = "Shipping methods, temperature restrictions, etc."
	shipping_locations = models.ManyToManyField(Location, blank=True, verbose_name="I will ship to")
	shipping_locations.help_text = "Check all locations you're willing to ship to"
	is_deleted = models.BooleanField(default=False)
	added_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name="added_by")
	added_by.help_text = "User who added this lot -- used for pre-registration discounts"
	category_automatically_added = models.BooleanField(default=False)
	category_checked = models.BooleanField(default=False)

	def save(self, *args, **kwargs):
		"""
		For in-person auctions, we'll generate a bidder_number-lot_number format
		"""
		if not self.custom_lot_number and self.auction:
			if self.auctiontos_seller:
				custom_lot_number = 1
				other_lots = self.auctiontos_seller.lots_qs
				for lot in other_lots:
					match = re.findall(r'\d+', f"{lot.custom_lot_number}")
					if match:
						# last string of digits found
						match = int(match[-1])
						if match >= custom_lot_number:
							custom_lot_number = match + 1
				self.custom_lot_number = f"{self.auctiontos_seller.bidder_number}-{custom_lot_number}"
		# a bit of magic to automatically set categories		
		fix_category = False
		if self.species_category:
			if self.species_category.pk == 21:
				fix_category = True
		if not self.species_category:
			fix_category = True
		if self.category_checked:
			fix_category = False
		if fix_category:
			self.category_checked = True
			if self.auction:
				if self.auction.use_categories:
					result = guess_category(self.lot_name)
					if result:
						self.species_category = result
						self.category_automatically_added = True
		if not self.reference_link: 
			search = self.lot_name.replace(" ","%20")
			self.reference_link = f"https://www.google.com/search?q={search}&tbm=isch"
		super().save(*args, **kwargs) 

	def __str__(self):
		return "" + str(self.lot_number_display) + " - " + self.lot_name

	def add_winner_message(self, user, tos, winning_price):
		"""Create a lot history message when a winner is declared (or changed)
		It's critical that this function is called every time the winner is changed so that invoices get recalculated"""
		LotHistory.objects.create(
			lot = self,
			user = user,
			message = f"{user.username} has set bidder {tos} as the winner of this lot (${winning_price}).",
			notification_sent = True,
			bid_amount = winning_price,
			changed_price=True,
			seen=True
		)
		invoice, created = Invoice.objects.get_or_create(auctiontos_user=tos, auction=self.auction, defaults={})
		invoice.recalculate

	def delete(self, *args, **kwargs):
		self.is_deleted=True
		self.save()

	@property
	def i_bred_this_fish_display(self):
		if self.i_bred_this_fish:
			return "Yes"
		else:
			return ""

	@property
	def seller_invoice_link(self):
		"""/invoices/123 for the auction/seller of this lot"""
		try:
			if self.auctiontos_seller:
				invoice = Invoice.objects.get(auctiontos_user=self.auctiontos_seller)
				return f'/invoices/{invoice.pk}'
		except:
			pass
		try:
			if self.user:
				invoice = Invoice.objects.get(user=self.user, auction=self.auction)
				return f'/invoices/{invoice.pk}'
		except:
			pass
		return ""
	
	@property
	def winner_invoice_link(self):
		"""/invoices/123 for the auction/winner of this lot"""
		try:
			if self.auctiontos_winner:
				invoice = Invoice.objects.get(auctiontos_user=self.auctiontos_winner)
				return f'/invoices/{invoice.pk}'
		except:
			pass
		try:
			if self.winner:
				invoice = Invoice.objects.get(user=self.winner, auction=self.auction)
				return f'/invoices/{invoice.pk}'
		except:
			pass
		return ""
			
	@property
	def tos_needed(self):
		if not self.auction:
			return False
		if self.auctiontos_seller:
			return False
		try:
			AuctionTOS.objects.get(user=self.user, auction=self.auction)
			return False
		except:
			return f'/auctions/{self.auction.slug}'

	@property
	def winner_location(self):
		"""String of location of the winner for this lot"""
		try:
			return str(self.auctiontos_winner.pickup_location)
		except:
			pass
		try:
			return str(AuctionTOS.objects.get(user=self.winner, auction=self.auction).pickup_location)
		except:
			pass
		return ""
	
	@property
	def location_as_object(self):
		"""Pickup location of the seller"""
		try:
			return self.auctiontos_seller.pickup_location
		except:
			pass
		try:
			return AuctionTOS.objects.get(user=self.user, auction=self.auction).pickup_location
		except:
			pass
		return None

	@property
	def location(self):
		"""String of location of the seller of this lot"""
		return str(self.location_as_object) or ""

	@property
	def seller_name(self):
		"""Full name of the seller of this lot"""
		if self.user:
			return self.user.first_name + " " + self.user.last_name
		if self.auctiontos_seller:
			return self.auctiontos_seller.name
		return "Unknown"

	@property
	def seller_email(self):
		"""Email of the seller of this lot"""
		if self.user:
			return self.user.email
		if self.auctiontos_seller:
			return self.auctiontos_seller.email
		return "Unknown"

	@property
	def winner_name(self):
		"""Full name of the winner of this lot"""
		if self.auctiontos_winner:
			return self.auctiontos_winner.name
		if self.winner:
			return self.winner.first_name + " " + self.winner.last_name
		return ""

	@property
	def winner_email(self):
		"""Email of the winner of this lot"""
		if self.auctiontos_winner:
			return self.auctiontos_winner.email
		if self.winner:
			return self.winner.email
		return ""

	@property
	def table_class(self):
		"""We need to color rows red if a winner is set without a price, or a price is set without a winner"""
		if self.auctiontos_winner and not self.winning_price:
			return 'table-danger'
		if not self.auctiontos_winner and self.winning_price:
			return 'table-danger'
		return ""
	# @property
	# def user_as_str(self):
	# 	"""String value of the seller of this lot"""
	# 	return str(self.user)

	@property
	def seller_as_str(self):
		"""String of the seller name or number, for use on lot pages"""
		if self.auctiontos_seller:
			return str(self.auctiontos_seller)
		if self.user:
			return str(self.user)
		return "Unknown"
	
	@property
	def high_bidder_display(self):
		if self.sealed_bid:
			return "Sealed bid"
		if self.winner_as_str:
			return self.winner_as_str
		if self.high_bidder:
			userData, userdataCreated = UserData.objects.get_or_create(
				user = self.high_bidder,
				defaults={},
			)
			if userData.username_visible:
				return str(self.high_bidder)
			else:
				return "Anonymous"
		return "No bids"

	@property
	def high_bidder_for_admins(self):
		if self.auctiontos_winner:
			return self.auctiontos_winner.display_name_for_admins
		if self.winner:
			return str(self.winner)
		if self.high_bidder:
			return str(self.high_bidder)
		return "No bids"

	@property
	def winner_as_str(self):
		"""String of the winner name or number, for use on lot pages"""
		if self.auctiontos_winner:
			return f"{self.auctiontos_winner}"
		if self.winner:
			userData, created = UserData.objects.get_or_create(
				user = self.winner,
				defaults={},
				)
			if userData.username_visible:
				return str(self.winner)
			else:
				return "Anonymous"
		return ""

	@property
	def sold(self):
		if self.winner or self.auctiontos_winner:
			if self.winning_price:
				return True
		return False

	@property
	def pre_registered(self):
		"""True if this lot will get a discount for being pre-registered"""
		if self.auction:
			if self.auction.pre_register_lot_discount_percent or self.auction.pre_register_lot_entry_fee_discount:
				if self.added_by and self.user:
					if self.added_by == self.user:
						return True
		return False

	@property
	def payout(self):
		"""Used for invoicing"""
		payout = {
			"ended": False,
			"sold": False,
			"winning_price": 0,
			"to_seller": 0,
			"to_club": 0,
			"to_site": 0,
			}
		if self.auction:
			if self.winning_price or not self.active:
			#if (self.auctiontos_winner and self.winning_price) or not self.active:
				# bidding has officially closed
				payout['ended'] = True
				if self.banned:
					return payout
				auction = self.auction
				#auction = Auction.objects.get(id=self.auction.pk)
				if self.sold:
					payout['sold'] = True
					payout['winning_price'] = self.winning_price
					if self.donation:
						clubCut = self.winning_price
						sellerCut = 0
					else:
						if self.auctiontos_seller and self.auctiontos_seller.is_club_member:
							percent_field = 'winning_bid_percent_to_club_for_club_members'
							fee_field = 'lot_entry_fee_for_club_members'
						else:
							percent_field = 'winning_bid_percent_to_club'
							fee_field = 'lot_entry_fee'
						if self.pre_registered:
							clubCut = ( self.winning_price * (getattr(auction, percent_field) - auction.pre_register_lot_discount_percent) / 100 ) + getattr(auction, fee_field) - auction.pre_register_lot_entry_fee_discount
						else:
							clubCut = ( self.winning_price * getattr(auction, percent_field) / 100 ) + getattr(auction, fee_field)
						sellerCut = self.winning_price - clubCut
					payout['to_club'] = clubCut
					payout['to_seller'] = sellerCut
				else:
					# did not sell
					if not self.donation:
						payout['to_club'] = auction.unsold_lot_fee # bill the seller even if the item didn't sell
						payout['to_seller'] = 0 - auction.unsold_lot_fee
					else:
						payout['to_club'] = 0 # don't bill for donations
						payout['to_seller'] = 0
				if self.promoted:
					payout['to_club'] += auction.lot_promotion_cost					
		return payout

	@property
	def your_cut(self):
		return self.payout['to_seller']

	@property
	def club_cut(self):
		return self.payout['to_club']

	@property
	def number_of_watchers(self):
		return Watch.objects.filter(lot_number=self.lot_number).count()

	@property
	def hard_end(self):
		"""The absolute latest a lot can end, even with dynamic endings"""
		dynamic_end = datetime.timedelta(minutes=60)
		if self.auction:
			return self.auction.dynamic_end
		# there is currently no hard endings on lots not associated with an auction
		# as soon as the lot is saved, date_end will be set to dynamic_end (by consumers.reset_lot_end_time)
		# a new field hard_end could be added to lot to accomplish this, but I do not think it makes sense to have a hard end at this point
		# collect stats from a couple auctions with dynamic endings and re-assess
		return self.date_end + dynamic_end

	@property
	def calculated_end(self):
		"""Return datetime object for when this lot will end.
		
		Important: in the case of a lot that is part of an in-person auction with no end time, this will return timezone.now()

		A good alternative is lot.calculated_end_for_templates which returns either a string or a datetime
		"""
		# for in-person auctions only
		if self.is_part_of_in_person_auction:
			return self.auction.date_start + datetime.timedelta(days=364)
		# online auctions update lot.date_end (rolling endings)
		if self.date_end:
			return self.date_end
		# I would hope we never get here...but it it theoretically possible that a bug could cause self.date_end to be blank
		return timezone.now()

	@property
	def calculated_end_for_templates(self):
		"""For models, use self.calculated_end which always returns a date
		But for places where a user can see this, we need a friendly reminder that the auction admin needs to manually end lots"""
		if self.is_part_of_in_person_auction:
			if self.winner_as_str and self.date_end:
				# a sold lot that's part of an in-person auction
				return self.date_end
			return "Ends when sold"
		else:
			return self.calculated_end

	@property
	def can_add_images(self):
		"""Yeah, go for it as long as the lot isn't sold"""
		if self.winning_price:
			return False
		return True

	@property
	def bids_can_be_removed(self):
		"""True or False"""
		# sometimes people use buy now, in which case self.ended = True, but the auction itself hasn't ended yet
		if self.auction and self.ended and not self.auction.closed:
			return True
		if self.ended:
			return False
		return True

	@property
	def can_be_edited(self):
		"""Check to see if this lot can be edited.
		This is needed to prevent people making lots a donation right before the auction ends
		Actually, by request from many people, there's nothing at all prventing that right at this moment..."""
		if self.high_bidder:
				return False
		if self.winner or self.auctiontos_winner:
			return False
		if self.auction:
			# if this lot is part of an auction, allow changes right up until lot submission ends
			if timezone.now() > self.auction.lot_submission_end_date:
				return False
		# if we are getting here, there are no bids or this lot is not part of an auction
		# lots that are not part of an auction can always be edited as long as there are no bids
		return True
	
	@property
	def can_be_deleted(self):
		"""Check to see if this lot can be deleted.
		This is needed to prevent people deleting lots that don't sell right before the auction ends"""
		if self.high_bidder:
			return False
		if self.winner or self.auctiontos_winner:
			return False
		if self.auction:
			# if this lot is part of an auction, allow changes until 24 hours before the lot submission end
			if timezone.now() > self.auction.lot_submission_end_date - datetime.timedelta(hours=24):
				return False
		# you have at most 24 hours to delete a lot
		if timezone.now() > self.date_posted + datetime.timedelta(hours=24):
			return False
		return True

	@property
	def bidding_allowed_on(self):
		"""bidding is not allowed on very new lots"""
		first_bid_date = self.date_posted + datetime.timedelta(minutes=20)
		if self.auction:
			if self.auction.date_start > first_bid_date:
				return self.auction.date_start
		return first_bid_date

	@property
	def bidding_error(self):
		"""Return false if bidding is allowed, or an error message.  Used when trying to bid on lots.
		"""
		if self.banned:
			if self.ban_reason:
				return f"This lot has been removed: {self.ban_reason}"
			return "This lot has been removed"
		if self.tos_needed:
			return "The creator of this lot has not confirmed their pickup location for this auction."
		if self.auction:
			if not self.auction.allow_bidding_on_lots:
				return "This auction doesn't allow online bidding"
			if not self.auction.started:
				return "Bidding hasn't opened yet for this auction"
		if self.deactivated:
			return "This lot has been deactivated by its owner"
		if self.bidding_allowed_on > timezone.now():
			difference = self.bidding_allowed_on - timezone.now()
			delta = difference.seconds
			unit = "second"
			if delta > 60:
				delta = delta // 60
				unit = "minute"
			if delta > 60:
				delta = delta // 60
				unit = "hour"
			if delta > 24:
				delta = delta // 24
				unit = "day"
			if delta != 1:
				unit += "s"
			return f"This lot is very new, you can bid on it in {delta} {unit}"
		return False

	@property
	def is_part_of_in_person_auction(self):
		# but, see https://github.com/iragm/fishauctions/issues/116
		# all we would need for this request is to configure Auction.date_end
		# and a new view to set it to X date (probably 1 minute in the future)
		# the biggest issue I see is lack of an undo on this option
		if self.auction:
			if self.auction.is_online:
				return False
			else:
				return True
		return False

	@property
	def ended(self):
		"""Used by the view for display of whether or not the auction has ended
		See also the database field active, which is set (based on this field) by a system job (endauctions.py)"""
		# lot attached to in person auctions do not end unless manually set
		if self.sold or self.banned or self.is_deleted:
			return True
		if self.is_part_of_in_person_auction:
			return False
		# all other lots end
		if timezone.now() > self.calculated_end:
			return True
		else:
			return False

	@property
	def minutes_to_end(self):
		"""Number of minutes until bidding ends, as an int.  Returns 0 if bidding has ended"""
		if self.is_part_of_in_person_auction:
			return 999
		timedelta = self.calculated_end - timezone.now()
		seconds = timedelta.total_seconds()
		if seconds < 0:
			return 0
		minutes = seconds // 60
		return minutes

	@property
	def ending_soon(self):
		"""2 hours before - used to send notifications about watched lots"""
		if self.is_part_of_in_person_auction:
			return False
		warning_date = self.calculated_end - datetime.timedelta(hours=2)
		if timezone.now() > warning_date:
			return True
		else:
			return False

	@property
	def ending_very_soon(self):
		"""
		If a lot is about to end in less than a minute, notification will be pushed to the channel
		"""
		if self.minutes_to_end < 1:
			return True
		return False

	@property
	def within_dynamic_end_time(self):
		"""
		Return true if a lot will end in the next 15 minutes.  This is used to update the lot end time when last minute bids are placed.
		"""
		if self.is_part_of_in_person_auction:
			return False
		if self.minutes_to_end < 15:
			return True
		else:
			return False

	@property
	def sealed_bid(self):
		if self.auction:
			if self.auction.sealed_bid:
				return True
		return False

	@property
	def price(self):
		"""Price display"""
		if self.winning_price:
			return self.winning_price
		return self.max_bid

	@property
	def max_bid(self):
		"""returns the highest bid amount for this lot - this number should not be visible to the public"""
		allBids = Bid.objects.filter(lot_number=self.lot_number, last_bid_time__lte=self.calculated_end, amount__gte=self.reserve_price).order_by('-amount', 'last_bid_time')[:2]
		try:
			# $1 more than the second highest bid
			bidPrice = allBids[0].amount
			return bidPrice
		except:
			#print("no bids for this item")
			return self.reserve_price

	@property
	def bids(self):
		"""Get all bids for this lot, highest bid first"""
		#bids = Bid.objects.filter(lot_number=self.lot_number, last_bid_time__lte=self.calculated_end, amount__gte=self.reserve_price).order_by('-amount', 'last_bid_time')
		bids = Bid.objects.filter(lot_number=self.lot_number, last_bid_time__lte=self.calculated_end, amount__gte=self.reserve_price).order_by('-amount', 'last_bid_time')
		return bids

	@property
	def high_bid(self):
		"""returns the high bid amount for this lot"""
		if self.winning_price:
			return self.winning_price
		if self.sealed_bid:
			try:
				bids = self.bids
				return self.bids[0].amount
			except:
				return 0
		else:
			try:
				bids = self.bids
				# highest bid is the winner, but the second highest determines the price
				if bids[0].amount == bids[1].amount:
					return bids[0].amount
				else:
					# this is the old method: 1 dollar more than the second highest bidder
					# this would cause an issue if someone was tied for high bidder, and increased their proxy bid
					bidPrice = bids[1].amount + 1
					# instead, we'll just return the second highest bid in the case of a tie
					#bidPrice = bids[1].amount
				return bidPrice
			except:
				#print("no bids for this item")
				return self.reserve_price

	@property
	def high_bidder(self):
		""" Name of the highest bidder """
		if self.banned:
			return False
		try:
			bids = self.bids
			return bids[0].user
		except:
			return False

	@property
	def all_page_views(self):
		"""Return a set of all users who have viewed this lot, and how long they looked at it for"""
		return PageView.objects.filter(lot_number=self.lot_number)

	@property
	def anonymous_views(self):
		return len(PageView.objects.filter(lot_number=self.lot_number, user_id__isnull=True))

	@property
	def page_views(self):
		"""Total number of page views from all users"""
		pageViews = self.all_page_views
		return len(pageViews)

	@property
	def number_of_bids(self):
		"""How many users placed bids on this lot?"""
		bids = Bid.objects.filter(lot_number=self.lot_number, bid_time__lte=self.calculated_end, amount__gte=self.reserve_price)
		return len(bids)
	
	@property
	def view_to_bid_ratio(self):
		"""A low number here represents something interesting but not wanted.  A high number (closer to 1) represents more interest"""
		if self.page_views:
			return self.number_of_bids / self.page_views
		else:
			return 0

	@property
	def chat_allowed(self):
		if not self.is_chat_allowed:
			return False
		if self.auction:
			if not self.auction.is_chat_allowed:
				return False
		date_chat_end = self.calculated_end + datetime.timedelta(minutes=60)
		if timezone.now() > date_chat_end:
			return False
		return True

	@property
	def image_count(self):
		"""Count the number of images associated with this lot"""
		return LotImage.objects.filter(lot_number=self.lot_number).count()

	@property
	def images(self):
		"""All images associated with this lot"""
		return LotImage.objects.filter(lot_number=self.lot_number).order_by('-is_primary', 'createdon')

	@property
	def thumbnail(self):
		try:
			return LotImage.objects.get(lot_number=self.lot_number, is_primary=True)
		except:
			pass
		return None

	def get_absolute_url(self):
		return f'/lots/{self.lot_number}/{self.slug}/'

	@property
	def lot_number_display(self):
		return self.custom_lot_number or self.lot_number

	@property
	def lot_link(self):
		"""Simplest link to access this lot with"""
		if self.custom_lot_number and self.auction:
			return f"/auctions/{self.auction.slug}/lots/{self.custom_lot_number}/{self.slug}/"
		return f'/lots/{self.lot_number}/{self.slug}/'

	@property
	def full_lot_link(self):
		"""Full domain name URL for this lot"""
		current_site = Site.objects.get_current()
		return f"{current_site.domain}{self.lot_link}"

	@property
	def qr_code(self):
		"""Full domain name URL used to for QR codes"""
		return f"{self.full_lot_link}?src=qr"

	@property
	def label_line_0(self):
		"""Used for printed labels"""
		result = f"<b>LOT: {self.lot_number_display}</b>"
		#if self.quantity > 1:
		result += f" QTY: {self.quantity}"
		if self.buy_now_price and not self.sold:
			result += f" ${self.buy_now_price}"
		return result

	@property
	def label_line_1(self):
		"""Used for printed labels"""
		result = f"{self.lot_name}"
		return result

	@property
	def label_line_2(self):
		"""Used for printed labels"""
		if self.auctiontos_winner:
			return f"Winner: {self.auctiontos_winner.name}"
		if self.auctiontos_seller:
			return f"Seller: {self.auctiontos_seller.name}"
		return ""

	@property
	def label_line_3(self):
		"""Used for printed labels"""
		result = ""
		if self.auction:
			if self.auction.multi_location:
				if self.auctiontos_winner.pickup_location:
					return self.auctiontos_winner.pickup_location
				else:
					# this is not sold -- allow the auctioneer to check the appropriate pickup location
					locations = self.auction.location_qs
					for location in locations:
						result += "  __" + location.short_name
		return result

	@property
	def seller_ip(self):
		try:
			return self.user.userdata.last_ip_address
		except:
			return None
	
	@property
	def bidder_ip_same_as_seller(self):
		if self.seller_ip:
			bids = Bid.objects.filter(lot_number__pk=self.pk, user__userdata__last_ip_address=self.seller_ip).count()
			if bids:
				return bids
		return None

	@property
	def reference_link_domain(self):
		if self.reference_link:
			pattern = r"https?://(?:www\.)?([a-zA-Z0-9.-]+)\.([a-zA-Z]{2,6})"
			# Use the regex pattern to find the matches in the URL
			match = re.search(pattern, self.reference_link)
			if match:
				base_domain = match.group(1)
				extension = match.group(2)
				return f"{base_domain}.{extension}"
		return ""

class Invoice(models.Model):
	"""
	An invoice is applied to an auction
	or a lot (if the lot is not associated with an auction)
	
	It's the total amount you owe and how much you owe to the club
	Invoices get rounded to the nearest dollar
	"""
	auction = models.ForeignKey(Auction, blank=True, null=True, on_delete=models.SET_NULL)
	lot = models.ForeignKey(Lot, blank=True, null=True, on_delete=models.SET_NULL)
	lot.help_text = "not used"
	# the user field is no longer used and can be removed in a future migration
	user = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL)
	auctiontos_user = models.ForeignKey(AuctionTOS, null=True, blank=True, on_delete=models.CASCADE, related_name="auctiontos")
	# the seller field is no longer used and can be removed in a future migration
	seller = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name="seller")
	date = models.DateTimeField(auto_now_add=True, blank=True)
	status = models.CharField(
		max_length=20,
		choices=(
			('DRAFT', 'Open'),
			('UNPAID', "Waiting for payment"),
			('PAID', "Paid"),
		),
		default="DRAFT"
	)
	opened = models.BooleanField(default=False)
	printed = models.BooleanField(default=False)
	email_sent = models.BooleanField(default=False)
	# this field should be removed in a future migration, although I think it may still be referenced in a few places
	seller_email_sent = models.BooleanField(default=False)
	adjustment_direction = models.CharField(
		max_length=20,
		choices=(
			('PAY_SELLER', 'Discount'),
			('PAY_CLUB', "Charge extra"),
		),
		default="PAY_CLUB"
	)
	adjustment = models.PositiveIntegerField(default = 0, validators=[MinValueValidator(0)])
	adjustment_notes = models.CharField(max_length=150, default="Corrected")
	no_login_link = models.CharField(max_length=255, default=uuid.uuid4, blank=True, verbose_name="This link will be emailed to the user, allowing them to view their invoice directly without logging in")
	calculated_total = models.IntegerField(null=True, blank=True)
	calculated_total.help_text = "This field is set automatically, you shouldn't need to manually change it"
	memo = models.CharField(max_length=500, blank=True, null=True, default="")
	memo.help_text = "Only other auction admins can see this"

	@property
	def recalculate(self):
		"""Store the current net in the calculated_total field.  Call this every time you add or remove a lot from this invoice"""
		self.calculated_total = self.rounded_net
		self.save()

	@property
	def total_adjustment_amount(self):
		"""There's a difference between the subtotal and the rounded net -- rounding, manual adjustments, fist bid payouts, etc"""
		return self.subtotal - self.rounded_net

	@property
	def subtotal(self):
		"""don't call this directly, use self.net or another property instead"""
		return self.total_sold - self.total_bought

	@property
	def first_bid_payout(self):
		try:
			if self.auction.first_bid_payout:
				if self.lots_bought:
					return self.auction.first_bid_payout
		except:
			pass
		return 0

	@property
	def net(self):
		"""Factor in:
		Total bought
		Total sold
		Any auction-wide payout promotions
		Any manual adjustments made to this invoice
		"""
		subtotal = self.subtotal
		# if this auction is using the first bid payout system to encourage people to bid
		subtotal += self.first_bid_payout
		if self.adjustment:
			if self.adjustment_direction == 'PAY_SELLER':
				subtotal += self.adjustment
			else:
				subtotal -= self.adjustment
		if not subtotal:
			subtotal = 0
		return subtotal

	@property
	def user_should_be_paid(self):
		"""Return true if the user owes the club money.  Most invoices will be negative unless the user is a vendor"""
		if self.net > 0:
			return True
		else:
			return False

	@property
	def rounded_net(self):
		"""Always round in the customer's favor (against the club) to make sure that the club doesn't need to deal with change, only whole dollar amounts"""
		rounded = round(self.net)
		#print(f"{self.net} Rounded to {rounded}")
		if self.user_should_be_paid:
			if self.net > rounded:
				# we rounded down against the customer
				return rounded + 1
			else:
				return rounded
		else:
			if self.net <= rounded:
				return rounded
			else:
				return rounded + 1

	@property
	def absolute_amount(self):
		"""Give the absolute value of the invoice's net amount"""
		return abs(self.rounded_net)

	@property
	def sold_lots_queryset(self):
		"""Simple qs containing all lots SOLD by this user in this auction"""
		return Lot.objects.filter(auctiontos_seller=self.auctiontos_user, auction=self.auction, is_deleted=False).order_by('lot_number')

	@property
	def bought_lots_queryset(self):
		"""Simple qs containing all lots BOUGHT by this user in this auction"""
		return Lot.objects.filter(auctiontos_winner=self.auctiontos_user, auction=self.auction, is_deleted=False).order_by('lot_number')

	@property
	def sold_lots_queryset_sorted(self):
		try:
			return sorted(self.sold_lots_queryset, key=lambda t: str(t.winner_location) ) 
		except:
			return self.sold_lots_queryset

	@property
	def lots_sold(self):
		"""Return number of lots the user attempted to sell in this invoice (unsold lots included)"""
		return len(self.sold_lots_queryset)

	@property
	def lots_sold_successfully(self):
		"""Queryset of lots the user sold in this invoice (unsold lots not included)"""
		return self.sold_lots_queryset.filter(auctiontos_winner__isnull=False)
	
	@property
	def lots_sold_successfully_count(self):
		"""Return number of lots the user sold in this invoice (unsold lots not included)"""
		return self.lots_sold_successfully.count()

	@property
	def lot_labels(self):
		"""For online auctions, only sold lots will have printed labels.  For in-person auctions, all submitted lots get printed"""
		if self.is_online:
			return self.lots_sold_successfully
		else:
			return self.sold_lots_queryset

	@property
	def unsold_lots(self):
		"""Return number of lots the user did not sell. This may be simply lots whose winner has not been set yet."""
		return len(self.sold_lots_queryset.exclude(auctiontos_winner__isnull=False))

	@property
	def unsold_non_donation_lots(self):
		"""For non-online auctions only.  Return number of lots the user did not sell. This may be simply lots whose winner has not been set yet."""
		if self.is_online:
			return 0
		return len(self.sold_lots_queryset.exclude(auctiontos_winner__isnull=False).filter(donation=False, banned=False))

	@property
	def total_sold(self):
		"""Seller's cut of all lots sold"""
		total_sold = 0
		for lot in self.sold_lots_queryset:
			total_sold += lot.your_cut
		return total_sold

	@property
	def lots_bought(self):
		"""Return number of lots the user bought in this invoice"""
		return len(self.bought_lots_queryset)

	@property
	def total_bought(self):
		#print(self.bought_lots_queryset.annotate(total=Sum('winning_price'))['total'])
		total_bought = 0
		for lot in self.bought_lots_queryset:
			if lot.winning_price:
				total_bought += lot.winning_price
		return total_bought

	@property
	def location(self):
		"""Pickup location selected by the user"""
		if self.auctiontos_user:
			return self.auctiontos_user.pickup_location
		try:
			return AuctionTOS.objects.get(user=self.user.pk, auction=self.auction.pk).pickup_location
		except:
			return None

	@property
	def contact_email(self):
		if self.location:
			if self.location.pickup_location_contact_email:
				return self.location.pickup_location_contact_email
		return self.auction.created_by.email

	@property
	def invoice_summary_short(self):
		result = ""
		if self.user_should_be_paid:
			result += " needs to be paid"
		else:
			result += " owes "
			if self.auction:
				result += "the club"
			elif self.seller:
				result += str(self.seller)
		return result + " $" + "%.2f" % self.absolute_amount

	@property
	def invoice_summary(self):
		try:
			base = str(self.auctiontos_user.name)
		except:
			try:
				base = str(self.user.first_name)
			except:
				base = "Unknown"
		return base + self.invoice_summary_short

	@property
	def label(self):
		if self.auction:
			return self.auction
		if self.seller:
			dateString = self.date.strftime("%b %Y")
			return f"{self.seller} {dateString}"
		return "Unknown"

	def __str__(self):
		if self.auctiontos_user:
			return f"{self.auctiontos_user.name}'s invoice for {self.auctiontos_user.auction}"
		if self.auction:
			return f"{self.user}'s invoice for {self.auction}"
		else:
			return f"{self.user}'s invoice from {self.seller}"
		#base = str(self.user)
		#if self.user_should_be_paid:
		#	base += " needs to be paid"
		#else:
		#	base += " owes the club"
		#return base + " $" + "%.2f" % self.absolute_amount
	
	def get_absolute_url(self):
		return f'/invoices/{self.pk}/'

	@property
	def is_online(self):
		"""Based on the auction associated with this invoice"""
		if self.auctiontos_user:
			return self.auctiontos_user.auction.is_online
		if self.auction:
			return self.auction.is_online
		return False

class Bid(models.Model):
	"""Bids apply to lots"""
	user = models.ForeignKey(User, on_delete=models.CASCADE)
	lot_number = models.ForeignKey(Lot, on_delete=models.CASCADE)
	bid_time = models.DateTimeField(auto_now_add=True, blank=True)
	last_bid_time = models.DateTimeField(auto_now_add=True, blank=True)
	amount = models.PositiveIntegerField(validators=[MinValueValidator(1)])
	was_high_bid = models.BooleanField(default=False)
	# note: there is not AuctionTOS field here - this means that bids can only be placed by Users
	# AuctionTOSs CAN be declared the winners of lots without placing a single bid
	# time will tell if this is a mistake or not

	def __str__(self):
		return str(self.user) + " bid " + str(self.amount) + " on lot " + str(self.lot_number)

class Watch(models.Model):
	"""
	Users can watch lots.
	This adds them to a list on the users page, and sends an email 2 hours before the auction ends
	"""
	user = models.ForeignKey(User, on_delete=models.CASCADE)
	lot_number = models.ForeignKey(Lot, on_delete=models.CASCADE)
	# not doing anything with createdon field right now
	# but might be interesting to track at what point in the auction users watch lots
	createdon = models.DateTimeField(auto_now_add=True, blank=True)

	def __str__(self):
		return str(self.user) + " watching " + str(self.lot_number)
	class Meta:
		verbose_name_plural = "Users watching"


class UserBan(models.Model):
	"""
	Users can ban other users from bidding on their lots
	This will prevent the banned_user from bidding on any lots or in auction auctions created by the owned user
	"""
	user = models.ForeignKey(User, on_delete=models.CASCADE)
	banned_user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='banned_user')
	createdon = models.DateTimeField(auto_now_add=True, blank=True)

	def __str__(self):
		return str(self.user) + " has banned " + str(self.banned_user)

class UserIgnoreCategory(models.Model):
	"""
	Users can choose to hide all lots from all views
	"""
	user = models.ForeignKey(User, on_delete=models.CASCADE)
	category = models.ForeignKey(Category, on_delete=models.CASCADE)
	createdon = models.DateTimeField(auto_now_add=True, blank=True)
	
	def __str__(self):
		return str(self.user) + " hates " + str(self.category)


class PageView(models.Model):
	"""Track what lots a user views, and how long they spend looking at each one"""
	user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
	auction = models.ForeignKey(Auction, null=True, blank=True, on_delete=models.CASCADE)
	auction.help_text = "Only filled out when a user views an auction's rules page"
	lot_number = models.ForeignKey(Lot, null=True, blank=True, on_delete=models.CASCADE)
	lot_number.help_text = "Only filled out when a user views a specific lot's page"
	date_start = models.DateTimeField(auto_now_add=True)
	date_end = models.DateTimeField(null=True,blank=True, default=timezone.now)
	total_time = models.PositiveIntegerField(default=0)
	total_time.help_text = 'The total time in seconds the user has spent on the lot page'
	source = models.CharField(max_length=200, blank=True, null=True, default="")
	counter = models.PositiveIntegerField(default=0)
	url = models.CharField(max_length=600, blank=True, null=True)
	title = models.CharField(max_length=600, blank=True, null=True)
	referrer = models.CharField(max_length=600, blank=True, null=True)
	session_id = models.CharField(max_length=600, blank=True, null=True)
	notification_sent = models.BooleanField(default=False)
	duplicate_check_completed = models.BooleanField(default=False)
	latitude = models.FloatField(default=0)
	longitude = models.FloatField(default=0)
	ip_address = models.CharField(max_length=100, blank=True, null=True) 
	user_agent = models.CharField(max_length=200, blank=True, null=True)
	platform = models.CharField(max_length=200, default = "", blank=True, null=True	)
	os = models.CharField(
		max_length=20,
		choices=(
			('UNKNOWN', 'Unknown'),
			('ANDROID', 'Android'),
			('IPHONE', "iPhone"),
			('WINDOWS', "Windows"),
			('OSX', "OS X"),
		),
		default="UNKNOWN"
	)

	def __str__(self):
		thing = self.url
		#thing = self.title
		return f"User {self.user} viewed {thing} for {self.total_time} seconds"

	@property
	def duplicates(self):
		"""Some duplciates have appeared and I can't figure out how it's possible"""
		return PageView.objects.filter(user=self.user,
				lot_number=self.lot_number,
            	url=self.url,
				auction=self.auction,
				session_id=self.session_id).exclude(pk=self.pk)
	
	@property
	def duplicate_count(self):
		return self.duplicates.count()

	@property
	def merge_and_delete_duplicate(self):
		if self.duplicate_count:
			dup = self.duplicates.first()
			if self.date_start > dup.date_start:
				self.date_start = dup.date_start
			if self.date_end and dup.date_end:
				if self.date_end < dup.date_end:
					self.date_end = dup.date_end
			self.total_time = self.total_time + dup.total_time
			if not self.source:
				self.source = dup.source
			self.counter = self.counter + dup.counter
			if dup.notification_sent:
				self.notification_sent = True
			if not self.title:
				self.title = dup.title
			if not self.referrer:
				self.referrer = dup.referrer
			self.save()
			dup.delete()

class UserLabelPrefs(models.Model):
	"""Dimensions used for the label PDF"""
	user = models.OneToOneField(User, on_delete=models.CASCADE)
	empty_labels = models.IntegerField(default = 0, validators=[MinValueValidator(0), MaxValueValidator(100)])
	empty_labels.help_text = "To print on partially used label sheets, print this many blank labels before printing the actual labels.  Just remember to set this back to 0 when starting a new sheet of labels!"
	page_width = models.FloatField(default = 8.5, validators=[MinValueValidator(1), MaxValueValidator(100.0)])
	page_height = models.FloatField(default = 11, validators=[MinValueValidator(1), MaxValueValidator(100.0)])
	label_width = models.FloatField(default = 2.51, validators=[MinValueValidator(1), MaxValueValidator(100.0)])
	label_height = models.FloatField(default = 0.98, validators=[MinValueValidator(0.4), MaxValueValidator(50.0)])
	label_margin_right = models.FloatField(default = 0.2, validators=[MinValueValidator(0.1), MaxValueValidator(5.0)])
	label_margin_bottom = models.FloatField(default = 0.02, validators=[MinValueValidator(0.0), MaxValueValidator(5.0)])
	page_margin_top = models.FloatField(default = 0.55, validators=[MinValueValidator(0.1)])
	page_margin_bottom = models.FloatField(default = 0.45, validators=[MinValueValidator(0.1)])
	page_margin_left = models.FloatField(default = 0.18, validators=[MinValueValidator(0.1)])
	page_margin_right = models.FloatField(default = 0.18, validators=[MinValueValidator(0.05)])
	font_size = models.FloatField(default = 8, validators=[MinValueValidator(5), MaxValueValidator(25)])
	UNITS = (
		('in', 'Inches'),
		('cm', 'Centimeters'),
	)
	unit = models.CharField(
		max_length=20,
		choices=UNITS,
		blank=False, null=False,
		default="in"
	)
	PRESETS = (
		('sm', 'Small (Avery 5160)'),
		('lg', 'Large (Avery 18262)'),
		('custom', 'Custom'),
	)
	preset = models.CharField(
		max_length=20,
		choices=PRESETS,
		blank=False, null=False,
		default="lg",
		verbose_name="Label size"
	)

class UserData(models.Model):
	"""
	Extension of user model to store additional info
	"""
	user = models.OneToOneField(User, on_delete=models.CASCADE)
	phone_number = models.CharField(max_length=20, blank=True, null=True)
	address = models.CharField(max_length=500, blank=True, null=True)
	address.help_text="Your complete mailing address.  If you sell lots in an auction, your check will be mailed here."
	location = models.ForeignKey(Location, blank=True, null=True, on_delete=models.SET_NULL)
	club = models.ForeignKey(Club, blank=True, null=True, on_delete=models.SET_NULL)
	use_dark_theme = models.BooleanField(default=True)
	use_dark_theme.help_text = "Uncheck to use the blindingly bright light theme"
	use_list_view = models.BooleanField(default=False)
	use_list_view.help_text = "Show a list of all lots instead of showing pictures"
	email_visible = models.BooleanField(default=False)
	email_visible.help_text = "Show your email address on your user page.  This will be visible only to logged in users.  <a href='/blog/privacy/' target='_blank'>Privacy information</a>"
	last_auction_used = models.ForeignKey(Auction, blank=True, null=True, on_delete=models.SET_NULL)
	last_activity = models.DateTimeField(auto_now_add=True)
	latitude = models.FloatField(default=0)
	longitude = models.FloatField(default=0)
	location_coordinates = PlainLocationField(based_fields=['address'], zoom=11, blank=True, null=True, verbose_name="Map")
	location_coordinates.help_text = "Make sure your map marker is correctly placed - you will get notifications about nearby auctions"
	last_ip_address = models.CharField(max_length=100, blank=True, null=True)
	email_me_when_people_comment_on_my_lots = models.BooleanField(default=True, blank=True)
	email_me_when_people_comment_on_my_lots.help_text = "Notifications will be sent once a day, only for messages you haven't seen"
	email_me_about_new_auctions = models.BooleanField(default=True, blank=True, verbose_name="Email me about new online auctions")
	email_me_about_new_auctions.help_text = "When new online auctions are created with pickup locations near my location, notify me"
	email_me_about_new_auctions_distance = models.PositiveIntegerField(null=True, blank=True, default=100, verbose_name="New online auction distance")
	email_me_about_new_auctions_distance.help_text = "miles, from your address"
	email_me_about_new_in_person_auctions = models.BooleanField(default=True, blank=True)
	email_me_about_new_in_person_auctions.help_text = "When new in-person auctions are created near my location, notify me"
	email_me_about_new_in_person_auctions_distance = models.PositiveIntegerField(null=True, blank=True, default=100, verbose_name="New in-person auction distance")
	email_me_about_new_in_person_auctions_distance.help_text = "miles, from your address"
	email_me_about_new_local_lots = models.BooleanField(default=True, blank=True)
	email_me_about_new_local_lots.help_text = "When new nearby lots (that aren't part of an auction) are created, notify me"
	local_distance = models.PositiveIntegerField(null=True, blank=True, default=60, verbose_name="New local lot distance")
	local_distance.help_text = "miles, from your address"
	email_me_about_new_lots_ship_to_location = models.BooleanField(default=True, blank=True, verbose_name="Email me about lots that can be shipped")
	email_me_about_new_lots_ship_to_location.help_text = "Email me when new lots are created that can be shipped to my location"
	paypal_email_address = models.CharField(max_length=200, blank=True, null=True, verbose_name="Paypal Address")
	paypal_email_address.help_text = "If different from your email address"
	unsubscribe_link = models.CharField(max_length=255, default=uuid.uuid4, blank=True)
	has_unsubscribed = models.BooleanField(default=False, blank=True)
	banned_from_chat_until = models.DateTimeField(null=True, blank=True)
	banned_from_chat_until.help_text = "After this date, the user can post chats again.  Being banned from chatting does not block bidding"
	can_submit_standalone_lots = models.BooleanField(default=True)
	dismissed_cookies_tos = models.BooleanField(default=False)
	show_ad_controls = models.BooleanField(default=False, blank=True)
	show_ad_controls.help_text = "Show a tab for ads on all pages"
	credit = models.DecimalField(max_digits=6, decimal_places=2, default=0)
	credit.help_text = "The total balance in your account"
	show_ads = models.BooleanField(default=True, blank=True)
	show_ads.help_text = "Ads have been disabled site-wide indefinitely, so this option doesn't do anything right now."
	preferred_bidder_number = models.CharField(max_length=4, default="", blank=True)
	timezone = models.CharField(max_length=100, null=True, blank=True)
	username_visible = models.BooleanField(default=True, blank=True)
	username_visible.help_text = "Uncheck to bid anonymously.  Your username will still be visible on lots you sell, chat messages, and to the people running any auctions you've joined."
	show_email_warning_sent = models.BooleanField(default=False, blank=True)
	show_email_warning_sent.help_text = "When a user has their email address hidden and sells a lot, this is checked"
	username_is_email_warning_sent = models.BooleanField(default=False, blank=True)
	username_is_email_warning_sent.help_text = "Warning email has been sent because this user made their username an email"
	send_reminder_emails_about_joining_auctions = models.BooleanField(default=True, blank=True)
	send_reminder_emails_about_joining_auctions.help_text = "Get an annoying reminder email when you view an auction but don't join it"

	# breederboard info
	rank_unique_species = models.PositiveIntegerField(null=True, blank=True)
	number_unique_species = models.PositiveIntegerField(null=True, blank=True)
	rank_total_lots = models.PositiveIntegerField(null=True, blank=True)
	number_total_lots = models.PositiveIntegerField(null=True, blank=True)
	rank_total_spent = models.PositiveIntegerField(null=True, blank=True)
	number_total_spent = models.PositiveIntegerField(null=True, blank=True)
	rank_total_bids = models.PositiveIntegerField(null=True, blank=True)
	number_total_bids = models.PositiveIntegerField(null=True, blank=True)
	number_total_sold = models.PositiveIntegerField(null=True, blank=True)
	rank_total_sold = models.PositiveIntegerField(null=True, blank=True)
	total_volume = models.PositiveIntegerField(null=True, blank=True)
	rank_volume = models.PositiveIntegerField(null=True, blank=True)
	seller_percentile = models.PositiveIntegerField(null=True, blank=True)
	buyer_percentile = models.PositiveIntegerField(null=True, blank=True)
	volume_percentile = models.PositiveIntegerField(null=True, blank=True)
	has_bid = models.BooleanField(default=False)
	has_used_proxy_bidding = models.BooleanField(default=False)
	
	def __str__(self):
		return f"{self.user.username}'s data"

	@property
	def my_lots_qs(self):
		"""All lots this user submitted, whether in an auction, or independently"""
		return Lot.objects.filter(Q(user=self.user)|Q(auctiontos_seller__user=self.user)).exclude(is_deleted=True)

	@property
	def lots_submitted(self):
		"""All lots this user has submitted, including unsold"""
		return self.my_lots_qs.count()

	@property
	def lots_sold(self):
		"""All lots this user has sold"""
		return self.my_lots_qs.filter(winner__isnull=False).count()

	@property
	def total_sold(self):
		"""Total amount this user has sold on this site"""
		total = 0
		for lot in self.my_lots_qs.filter(winning_price__isnull=False):
			total += lot.winning_price
		return total

	@property
	def species_sold(self):
		"""Total different species that this user has bred and sold in auctions"""
		print("species_sold is is no longer used, there's no way for users to enter species information anymore")
		allLots = self.my_lots_qs.filter(i_bred_this_fish=True,winner__isnull=False).values('species').distinct().count()
		return allLots

	@property
	def my_won_lots_qs(self):
		"""All lots won by this user, in an auction or independently"""
		return Lot.objects.filter(Q(winner=self.user)|Q(auctiontos_winner__user=self.user), winning_price__isnull=False).exclude(is_deleted=True)

	@property
	def lots_bought(self):
		"""Total number of lots this user has purchased"""
		return self.my_won_lots_qs.count()
	
	@property
	def total_spent(self):
		"""Total amount this user has spent on this site"""
		total = 0
		for lot in self.my_won_lots_qs:
			total += lot.winning_price
		return total

	@property
	def calc_total_volume(self):
		"""Bought + sold"""
		return self.total_spent + self.total_sold

	@property
	def total_bids(self):
		"""Total number of successful bids this user has placed (max one per lot)"""
		#return len(Bid.objects.filter(user=self.user, was_high_bid=True))
		return len(Bid.objects.filter(user=self.user))

	@property
	def lots_viewed(self):
		"""Total lots viewed by this user"""
		return len(PageView.objects.filter(user=self.user.pk))
	
	@property
	def bought_to_sold(self):
		"""Ratio of lots bought to lots sold"""
		if self.lots_sold:
			return self.lots_bought / self.lots_sold
		else:
			return 0
	
	@property
	def bid_to_view(self):
		"""Ratio of lots viewed to lots bought.  Lower number is indicative of tire kicking, higher number means business"""
		if self.lots_viewed:
			return self.total_bids / self.lots_viewed 
		else:
			return 0

	@property
	def viewed_to_sold(self):
		"""Ratio of lots viewed to lots sold"""
		if self.lots_viewed:
			return self.lots_sold / self.lots_viewed
		else:
			return 0

	@property
	def dedication(self):
		"""Ratio of bids to won lots"""
		if self.lots_bought:
			return self.lots_bought / self.total_bids
		else:
			return 0
	
	@property
	def percent_success(self):
		"""Ratio of bids to won lots, formatted"""
		return self.dedication * 100
	
	@property
	def positive_feedback_as_seller(self):
		return self.my_lots_qs.filter(feedback_rating=1).count()

	@property
	def negative_feedback_as_seller(self):
		return self.my_lots_qs.filter(feedback_rating=-1).count()

	@property
	def percent_positive_feedback_as_seller(self):
		positive = self.positive_feedback_as_seller
		negative = self.negative_feedback_as_seller
		if not negative:
			return 100
		return int(( positive / (positive + negative) ) * 100)

	@property
	def positive_feedback_as_winner(self):
		return self.my_won_lots_qs.filter(winner_feedback_rating=1).count()

	@property
	def negative_feedback_as_winner(self):
		return self.my_won_lots_qs.filter(winner_feedback_rating=-1).count()

	@property
	def percent_positive_feedback_as_winner(self):
		positive = self.positive_feedback_as_winner
		negative = self.negative_feedback_as_winner
		if not negative:
			return 100
		return int(( positive / (positive + negative) ) * 100)

class UserInterestCategory(models.Model):
	"""
	How interested is a user in a given category
	"""
	user = models.ForeignKey(User, on_delete=models.CASCADE)
	category = models.ForeignKey(Category, on_delete=models.CASCADE)
	interest = models.PositiveIntegerField(default=0, validators=[MinValueValidator(0)])
	as_percent = models.PositiveIntegerField(default=0, validators=[MinValueValidator(0), MaxValueValidator(100)])

	def __str__(self):
		return f"{self.user} interest level in {self.category} is {self.as_percent}"

	def save(self, *args, **kwargs):
		"""
		Normalize the user's interest in a category relative to all of this user's interests
		"""
		try:
			maxInterest = UserInterestCategory.objects.filter(user=self.user).order_by('-interest')[0].interest
			self.as_percent = int(((self.interest + 1) / maxInterest) * 100) # + 1 for the times maxInterest is 0
			if self.as_percent > 100:
				self.as_percent = 100
		except Exception as e:
			self.as_percent = 100
		super().save(*args, **kwargs) 

class LotHistory(models.Model):
	lot = models.ForeignKey(Lot, blank=True, null=True, on_delete=models.CASCADE)
	user = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL)
	user.help_text = "The user who posted this message."
	message = models.CharField(max_length=400, blank=True, null=True)
	timestamp = models.DateTimeField(auto_now_add=True)
	seen = models.BooleanField(default=False)
	seen.help_text = "Has the lot submitter seen this message?"
	current_price = models.PositiveIntegerField(null=True, blank=True)
	current_price.help_text = "Price of the lot immediately AFTER this message"
	changed_price = models.BooleanField(default=False)
	changed_price.help_text = "Was this a bid that changed the price?"
	notification_sent = models.BooleanField(default=False)
	notification_sent.help_text = "Set to true automatically when the notification email is sent"
	bid_amount = models.PositiveIntegerField(null=True, blank=True)
	bid_amount.help_text = "For any kind of debugging"
	removed = models.BooleanField(default=False)

	def __str__(self):
		if self.message:
			return f"{self.message}"
		else:
			return "message"

	class Meta:
		verbose_name_plural = "Chat history"
		verbose_name = "Chat history"
		ordering = ['timestamp']


class AdCampaignGroup(models.Model):
	title = models.CharField(max_length=100, default="Untitled campaign")
	contact_user = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL)
	paid = models.BooleanField(default=False)
	total_cost = models.FloatField(default = 0)
	
	def __str__(self):
		return f"{self.title}"

	@property
	def number_of_clicks(self):
		"""..."""
		return AdCampaignResponse.objects.filter(campaign__campaign_group=self.pk, clicked=True).count()

	@property
	def number_of_impressions(self):
		"""How many times ads in this campaign group have been viewed"""
		return AdCampaignResponse.objects.filter(campaign__campaign_group=self.pk).count()

	@property
	def click_rate(self):
		"""What percent of views result in a click"""
		return (self.number_of_clicks/(self.number_of_impressions+1))*100
	
	@property
	def number_of_campaigns(self):
		"""How many campaigns are there in this group"""
		return AdCampaign.objects.filter(campaign_group=self.pk).count()

class AdCampaign(models.Model):
	image = ThumbnailerImageField(upload_to='images/', blank=True)
	campaign_group = models.ForeignKey(AdCampaignGroup, null=True, blank=True, on_delete=models.SET_NULL)
	title = models.CharField(max_length=50, default="Click here")
	text = models.CharField(max_length=40, blank=True, null=True)
	body_html = models.CharField(max_length=300, default="")
	external_url = models.URLField(max_length = 300)
	begin_date = models.DateTimeField(blank=True, null=True)
	end_date = models.DateTimeField(blank=True, null=True)
	max_ads = models.PositiveIntegerField(default=10000000, validators=[MinValueValidator(0), MaxValueValidator(10000000)])
	max_clicks = models.PositiveIntegerField(default=10000000, validators=[MinValueValidator(0), MaxValueValidator(10000000)])
	category = models.ForeignKey(Category, null=True, blank=True, on_delete=models.SET_NULL, verbose_name="Category")
	category.help_text = "If set, this ad will only be shown to users interested in this particular category"
	auction = models.ForeignKey(Auction, blank=True, null=True, on_delete=models.SET_NULL)
	auction.help_text = "If set, this campaign will only be run on a particular auction (leave blank for site-wide)"
	bid = models.FloatField(default = 1)
	bid.help_text = "At the moment, this is not actually the cost per click, it's the percent chance of showing this ad.  If the top ad fails, the next one will be selected.  If there are none left, google ads will be loaded.  Expects 0-1"
	
	def __str__(self):
		if self.campaign_group:
			return f"{self.campaign_group.title} - {self.title} ({self.click_rate:.2f}% clicked)"
		return f"{self.title}"

	@property
	def number_of_clicks(self):
		"""..."""
		return AdCampaignResponse.objects.filter(campaign=self.pk, clicked=True).count()

	@property
	def number_of_impressions(self):
		"""How many times this ad has been viewed"""
		return AdCampaignResponse.objects.filter(campaign=self.pk).count()

	@property
	def click_rate(self):
		"""What percent of views result in a click"""
		return (self.number_of_clicks/(self.number_of_impressions+1))*100

class AdCampaignResponse(models.Model):
	campaign = models.ForeignKey(AdCampaign, on_delete=models.CASCADE)
	responseid = models.CharField(max_length=255, default=uuid.uuid4, blank=True)
	user = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL)
	session = models.CharField(max_length=250, blank=True, null=True)
	text = models.CharField(max_length=250, blank=True, null=True)
	timestamp = models.DateTimeField(auto_now_add=True)
	clicked = models.BooleanField(default=False)

	def __str__(self):
		if self.user:
			user = self.user
		else:
			user = "Anonymous"
		if self.clicked:
			action = "clicked"
		else:
			action = "viewed"
		return f"{user} {action}"

class AuctionCampaign(models.Model):
	auction = models.ForeignKey(Auction, null=True, blank=True, on_delete=models.SET_NULL)
	uuid = models.CharField(max_length=255, default=uuid.uuid4, blank=True)
	user = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL)
	email = models.CharField(max_length=255, default="", blank=True)
	timestamp = models.DateTimeField(auto_now_add=True)
	source = models.CharField(max_length=200, blank=True, null=True, default="")
	result = models.CharField(
		max_length=20,
		choices=(
			('ERR', 'No email sent'),
			('NONE', 'No response'),
			('VIEWED', "Clicked"),
			('JOINED', 'Joined'),
		),
		default="NONE"
	)
	email_sent = models.BooleanField(default=False)

	@property
	def link(self):
		current_site = Site.objects.get_current()
		return f"{current_site.domain}auctions/{self.uuid}"

class LotImage(models.Model):
	"""An image that belongs to a lot.  Each lot can have multiple images"""
	PIC_CATEGORIES = (
		('ACTUAL', 'This picture is of the exact item'),
		('REPRESENTATIVE', "This is my picture, but it's not of this exact item.  e.x. This is the parents of these fry"),
		('RANDOM', 'This picture is from the internet'),
	)
	lot_number = models.ForeignKey(Lot, on_delete=models.CASCADE)
	caption = models.CharField(max_length=60, blank=True, null=True)
	caption.help_text = "Optional"
	image = ThumbnailerImageField(upload_to='images/', blank=False, null=False)
	image.help_text = "Select an image to upload"
	image_source = models.CharField(
		max_length=20,
		choices=PIC_CATEGORIES,
		blank=True
	)
	is_primary = models.BooleanField(default=False, blank=True)
	createdon = models.DateTimeField(auto_now_add=True)

class FAQ(models.Model):
	"""Questions...constantly questions.  Maintained in the admin site, and used only on the FAQ page"""
	category_text = models.CharField(max_length=100)
	question = models.CharField(max_length=200)
	answer = MarkdownField(rendered_field='answer_rendered', validator=VALIDATOR_STANDARD, blank=True, null=True)
	answer.help_text = "To add a link: [Link text](https://www.google.com)"
	answer_rendered = RenderedMarkdownField(blank=True, null=True)
	slug = AutoSlugField(populate_from='question', unique=True)
	createdon = models.DateTimeField(auto_now_add=True)
	include_in_auctiontos_confirm_email = models.BooleanField(default=False, blank=True)

class SearchHistory(models.Model):
	"""To keep track of what people are searching for"""
	user = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL)
	search = models.CharField(max_length=600)
	createdon = models.DateTimeField(auto_now_add=True)
	auction = models.ForeignKey(Auction, null=True, blank=True, on_delete=models.SET_NULL)

@receiver(pre_save, sender=Auction)
def on_save_auction(sender, instance, **kwargs):
	"""This is run when an auction is saved"""
	if instance.date_end and instance.date_start:
    	# if the user entered an end time that's after the start time
		if instance.date_end < instance.date_start:
			new_start = instance.date_end
			instance.date_end = instance.date_start
			instance.date_start = new_start
	if not instance.date_end:
		if instance.is_online:
			instance.date_end = instance.date_start + datetime.timedelta(days=7)
	if not instance.lot_submission_end_date:
		if instance.is_online:
			instance.lot_submission_end_date = instance.date_end
		else:
			instance.lot_submission_end_date = instance.date_start
	if not instance.lot_submission_start_date:
		if instance.is_online:
			instance.lot_submission_start_date = instance.date_start
		else:
			instance.lot_submission_start_date = instance.date_start - datetime.timedelta(days=7)
	# if the lot submission end date is badly set, fix it
	if instance.is_online:
		if instance.lot_submission_end_date > instance.date_end:
			instance.lot_submission_end_date = instance.date_end
		if instance.lot_submission_start_date > instance.date_start:
			instance.lot_submission_start_date = instance.date_start
	# I don't see a problem submitting lots after the auction has started,
	# or any need to restrict when people add lots to an in-person auction
	# So I am not putting any new validation checks here
	
	# if this is an existing auction
	if instance.pk:
		#print('updating date end on lots because this is an existing auction')
		# update the date end for all lots associated with this auction
		# note that we do NOT update the end time if there's a winner!
		# This means you cannot reopen an auction simply by changing the date end
		if instance.date_end:
			if instance.date_end + datetime.timedelta(minutes=60) < timezone.now():
				# if we are at least 60 minutes before the auction end
				lots = Lot.objects.exclude(is_deleted=True).filter(auction=instance.pk, winner__isnull=True, auctiontos_winner__isnull=True, active=True)
				for lot in lots:
					lot.date_end = instance.date_end
					lot.save()
	else:
		# logic for new auctions goes here
		pass
	#print(instance.date_start)
	if not instance.is_online:
		# for in-person auctions, we need to add a single pickup location
		# and create it if the user was dumb enough to delete it
		try:
			in_person_location, created = PickupLocation.objects.get_or_create(
				auction = instance,
				is_default = True,
				defaults={
					'name': str(instance)[:50],
					'pickup_time':instance.date_start,
					},
			)
		except:
			print("Somehow there's two pickup locations for this auction -- how is this possible?")

@receiver(pre_save, sender=UserData)
@receiver(pre_save, sender=PickupLocation)
@receiver(pre_save, sender=Club)
def update_user_location(sender, instance, **kwargs):
	"""
	GeoDjango does not appear to support MySQL and Point objects well at the moment (2020)
	To get around this, I'm storing the coordinates in a raw latitude and longitude column

	The custom function distance_to is used to annotate queries

	It is bad practice to use a signal in models.py,
	however with just a couple signals it makes more sense to have them here than to add a whole separate file for it
	"""
	try:
		#if not instance.latitude and not instance.longitude:
		# some things to change here:
		# if sender has coords and they do not equal the instance coords, update instance lat/lng from sender
		# if sender has lat/lng and they do not equal the instance lat/lng, update instance coords
		cutLocation = instance.location_coordinates.split(',')
		instance.latitude = float(cutLocation[0])
		instance.longitude = float(cutLocation[1])
	except:
		pass

@receiver(pre_save, sender=Lot)
def update_lot_info(sender, instance, **kwargs):
	"""
	Fill out the location and address from the user
	Fill out end date from the auction
	"""
	if not instance.pk:
		# new lot?  set the default end date to the auction end
		if instance.auction:
			instance.date_end = instance.auction.date_end
	if instance.user:
		userData, created = UserData.objects.get_or_create(
			user = instance.user,
			defaults={},
			)
		instance.latitude = userData.latitude
		instance.longitude = userData.longitude
		instance.address = userData.address
	
	# create an invoice for this seller/winner
	if instance.auction and instance.auctiontos_seller:
		invoice, created = Invoice.objects.get_or_create(auctiontos_user=instance.auctiontos_seller, auction=instance.auction, defaults={})
	if instance.auction and instance.auctiontos_winner:
		invoice, created = Invoice.objects.get_or_create(auctiontos_user=instance.auctiontos_winner, auction=instance.auction, defaults={})
	# This is probably too slow; instead invoices are recalculated when viewing or exporting
	# if invoice:
	# 	if instance.winning_price:
	# 		invoice.recalculate
	if instance.pk:
		original_instance = Lot.objects.get(pk=instance.pk)
		if not original_instance.banned and instance.banned:
			LotHistory.objects.create(
				lot = instance,
				user = None,
				message = 'This lot has been removed',
				changed_price = True,
				current_price=instance.high_bid,
				)
	if instance.auction and instance.reserve_price < instance.auction.minimum_bid:
		instance.reserve_price = instance.auction.minimum_bid

@receiver(user_logged_in)
def user_logged_in_callback(sender, user, request, **kwargs):
	"""When a user signs in, check for any AuctionTOS that have this users email but no user, and attach them to the user
	This allows people to view invoices, leave feedback, get contact information for sellers, etc.
	Important to have this be any user, not just new ones so that existing users can be signed up for in-person auctions"""
	auctiontoss = AuctionTOS.objects.filter(user__isnull=True, email=user.email)
	for auctiontos in auctiontoss:
		auctiontos.user = user
		auctiontos.save()