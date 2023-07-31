from django.conf import settings
from django.urls import include, path, re_path
from django.contrib import admin
from . import views
from django.contrib.auth.decorators import login_required
from django.views.generic.base import TemplateView

urlpatterns = [
    path('api/auctiontos-autocomplete/', views.AuctionTOSAutocomplete.as_view(), name='auctiontos-autocomplete'),
    path('api/lot-autocomplete/', views.LotAutocomplete.as_view(), name='lot-autocomplete'),
    path('ads/fetch/', views.RenderAd.as_view(), name='get_ad'),
    path('ads/<str:uuid>/', views.ClickAd.as_view(), name='click_ad'),
    path('api/payinvoice/<int:pk>/<str:status>', login_required(views.invoicePaid)),
    path('api/watchitem/<int:pk>/', login_required(views.watchOrUnwatch)),
    path('api/species/', login_required(views.getSpecies)),
    path('api/clubs/', login_required(views.getClubs)),
    path('api/lots/deactivate/<int:pk>/', views.lotDeactivate),
    path('api/images/rotate/', views.imagesRotate),
    path('api/images/primary/', views.imagesPrimary),
    path('api/lots/get_recommended/', views.RecommendedLots.as_view()),
    path('api/pageview/', views.pageview, name='pageview'),
    #path('api/pageview/<int:pk>/new/', views.pageview),
    path('api/feedback/<int:pk>/<str:leave_as>/', views.feedback),
    path('api/users/ban/<int:pk>/', views.userBan),
    path('api/users/unban/<int:pk>/', views.userUnban),
    path('api/users/location/', views.setCoordinates),
    path('api/users/lot_notifications/', views.lotNotifications),
    path('api/users/auction_notifications/', views.auctionNotifications),
    path('api/lots/new_lot_last_auction/', views.no_lot_auctions),
    path('api/chart/lots/<int:pk>/', views.LotChartView.as_view()),
    path('api/chart/users/<int:pk>/', views.UserChartView.as_view()),
    path('api/chart/auction/', views.AuctionChartView.as_view()),
    path('api/lot/<int:pk>/', views.LotAdmin.as_view(), name="auctionlotadmin"),
    path('api/auctiontos/<str:pk>/', views.AuctionTOSAdmin.as_view(), name="auctiontosadmin"),
    path('api/auctiontos/<str:pk>/delete', views.AuctionTOSDelete.as_view(), name="auctiontosdelete"),
    path('api/userignorecategory/create/<int:pk>/', views.CreateUserIgnoreCategory.as_view()),
    path('api/userignorecategory/delete/<int:pk>/', views.DeleteUserIgnoreCategory.as_view()),
    path('api/userignorecategory/', views.GetUserIgnoreCategory.as_view()),
    path('api/ignore_auction/', views.ignoreAuction),
    path('leaderboard/', views.Leaderboard.as_view()),
    path('clubs/', views.ClubMap.as_view(), name='clubs'),
    path('usermap/', views.UserMap.as_view(), name='admin_user_map'),
    path('dashboard/', views.AdminDashboard.as_view(), name='admin_dashboard'),
    path('tos/', views.UserAgreement.as_view(), name='tos'),
    path("robots.txt", TemplateView.as_view(template_name="robots.txt", content_type="text/plain"),),
    path("ads.txt", TemplateView.as_view(template_name="ads.txt", content_type="text/plain"),),
    path('lots/recommended/', views.AllRecommendedLots.as_view()),
    path('lots/', views.AllLots.as_view(), name='allLots'),
    path('lots/<int:pk>/', views.ViewLot.as_view(), name="lot_by_pk"),
    path('lots/edit/<int:pk>/', login_required(views.LotUpdate.as_view()), name='edit_lot'),
    path('lots/delete/<int:pk>/', views.LotDelete.as_view()),
    path('lots/new/', login_required(views.LotCreateView.as_view()), name='new_lot'),
    path('lots/watched/', login_required(views.MyWatched.as_view()), name='watched'),
    path('lots/won/', login_required(views.MyWonLots.as_view()), name="won_lots"),
    path('selling', login_required(views.MyLots.as_view()), name='selling'),
    path('lots/all/', views.AllLots.as_view(), name='allLots'),
    path('lots/user/', views.LotsByUser.as_view(), name="user_lots"),
    path('lots/<int:pk>/<slug:slug>/', views.ViewLot.as_view()),
    path('bids/', login_required(views.MyBids.as_view()), name="my_bids"),
    path('bids/delete/<int:pk>/', views.BidDelete.as_view()),
    path('', views.toDefaultLandingPage),
    path('old_about/', views.aboutSite, name='about'),
    path('about/', views.promoSite, name='promo'),
    path('account/', views.toAccount, name='account'),
    path('invoices/', login_required(views.Invoices.as_view()), name='my_invoices'),
    path('invoices/<int:pk>/', login_required(views.InvoiceView.as_view())),
    path('invoices/<int:pk>/labels', login_required(views.InvoiceLabelView.as_view())),
    path('invoices/example/', views.InvoiceView.as_view()),
    path('invoices/<uuid:uuid>/', views.InvoiceNoLoginView.as_view()),
    path('invoices/<uuid:uuid>/labels/', views.InvoiceLabelNoLoginView.as_view()),
    path('images/add_image/<int:lot>/', login_required(views.ImageCreateView.as_view()), name='add_image'),
    path('images/<int:pk>/delete/', views.ImageDelete.as_view(), name="delete_image"),
    path('images/<int:pk>/edit', views.ImageUpdateView.as_view(), name="edit_image"),
    path('auctions/', views.allAuctions.as_view(), name='auctions'),
    path('auctions/all/', views.allAuctions.as_view()),
    #path('auctions/new/', views.createAuction, name='createAuction'),
    path('auctions/new/', login_required(views.AuctionCreateView.as_view())),
    path('auctions/<slug:slug>/edit/', views.AuctionUpdate.as_view()),
    path('auctions/<slug:slug>/invoices/', login_required(views.AuctionInvoices.as_view())),
    path('auctions/<slug:slug>/invoice/', login_required(views.InvoiceViewNoExampleMode.as_view()), name='my_auction_invoice'),
    path('auctions/<slug:slug>/print-my-labels/', login_required(views.LotLabelView.as_view()), name="print_my_labels"),
    path('auctions/<slug:slug>/print/user/<str:username>/', login_required(views.LotLabelView.as_view())),
    path('auctions/<slug:slug>/print/bidder/<str:bidder_number>/', login_required(views.LotLabelView.as_view()), name="print_labels_by_bidder_number"),
    path('auctions/<slug:slug>/users/', login_required(views.AuctionUsers.as_view()), name="auction_tos_list"),
    path('auctions/<slug:slug>/users/bulk-add/', login_required(views.BulkAddUsers.as_view()), name="bulk_add_users"),
    path('auctions/<slug:slug>/users/<str:bidder_number>/', login_required(views.BulkAddLots.as_view()), name="bulk_add_lots"),
    path('auctions/<slug:slug>/lots/bulk-add/', login_required(views.BulkAddLots.as_view()), name="bulk_add_lots_for_myself"),
    path('auctions/<slug:slug>/lots/set-winners/', login_required(views.SetLotWinner.as_view()), name='auction_lot_winners'),
    path('auctions/<slug:slug>/lots/set-winners/autocomplete', views.QuickSetLotWinner.as_view(), name='auction_lot_winners_autocomplete'),
    path('auctions/<slug:slug>/lots/<slug:custom_lot_number>/', views.ViewLot.as_view()),
    path('auctions/<slug:slug>/lots/<slug:custom_lot_number>/<slug:lot_slug>/', views.ViewLot.as_view()),
    path('auctions/<slug:slug>/lots/', views.AuctionLots.as_view(), name="auction_lot_list"),
    path('auctions/<slug:slug>/stats/', login_required(views.AuctionStats.as_view())),
    path('auctions/<slug:slug>/report/', views.auctionReport, name="user_list"),
    path('selling/csv/', views.my_lot_report, name="my_lot_report"),
    path('auctions/<slug:slug>/lotlist/', views.auctionLotList, name="lot_list"),
    path('auctions/<slug:slug>/delete/', views.AuctionDelete.as_view()),
    path('auctions/<slug:slug>/chat/', views.AuctionChats.as_view()),
    path('auctions/<slug:slug>/paypal/<int:chunk>/', views.auctionInvoicesPaypalCSV),
    path('auctions/<slug:slug>/', views.AuctionInfo.as_view(), name="auction_main"),
    path('users/<str:slug>/', views.UserByName.as_view(), name='userpage'),
    path('user/<str:slug>/', views.UserByName.as_view()),
    path('u/<str:slug>/', views.UserByName.as_view()),
    path('store/<str:slug>/', views.UserByName.as_view()),
    #path('users/<int:pk>/location/', views.UserLocationUpdate.as_view()),
    path('username/', login_required(views.UsernameUpdate.as_view()), name='change_username'),
    #path('users/<int:pk>/preferences/', views.UserPreferencesUpdate.as_view()),
    path('ignore/', login_required(views.IgnoreCategoriesView.as_view()), name='ignore_categories'),
    path('contact_info/', login_required(views.UserLocationUpdate.as_view()), name='contact_info'),
    path('preferences/', login_required(views.UserPreferencesUpdate.as_view()), name='preferences'),
    path('printing/', login_required(views.UserLabelPrefsView.as_view()), name='printing'),
    path('faq/', views.FAQ.as_view(), name='faq'),
    path('auctions/<slug:slug>/locations/', views.PickupLocations.as_view(), name='auction_pickup_location'),
    path('auctions/<slug:slug>/locations/new/', views.PickupLocationsCreate.as_view(), name="create_auction_pickup_location"),
    #path('locations/', views.PickupLocations.as_view(), name='PickupLocation'),
    #path('locations/new/', views.PickupLocationsCreate.as_view()),
    path('locations/edit/<int:pk>/', views.PickupLocationsUpdate.as_view(), name='edit_pickup'),
    path('locations/<int:pk>/incoming-lots', views.PickupLocationsIncoming.as_view(), name='location_incoming'),
    path('locations/<int:pk>/outgoing-lots', views.PickupLocationsOutgoing.as_view(), name='location_outgoing'),
    path('locations/delete/<int:pk>/', views.PickupLocationsDelete.as_view(), name='delete_pickup'),
    path('blog/<slug:slug>/', views.BlogPostView.as_view()),
    path('feedback/', views.LeaveFeedbackView.as_view(), name='feedback'),
    path('unsubscribe/<slug:slug>/', views.UnsubscribeView.as_view()),
]