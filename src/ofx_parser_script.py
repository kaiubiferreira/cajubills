import pandas as pd
from ofxparse import OfxParser
import os
import glob # For finding files

# Define column names for consistency
COLUMN_ID = 'id'
COLUMN_DATE = 'date'
COLUMN_TYPE = 'type'
COLUMN_AMOUNT = 'amount'
COLUMN_MEMO = 'memo'
COLUMN_ACCOUNT_TYPE = 'account_type'
COLUMN_CATEGORY = 'category' # New column for categorization

# --- Categorization Rules ---
# Rules are processed in order. The first match wins.
# Each rule is a tuple: (list_of_keywords, category_name)
# All keywords in the list must be present in the memo (case-insensitive AND condition).
CATEGORIZATION_RULES = [
    # --- Highly Specific Payee/Transfer Rules (Revised for better Investment/Kaiubi logic) ---
    # Kaiubi Transfers SENT to specific Investment Institutions
    (['transferência enviada', 'kaiubi', 'xp invest'], 'Investments'),
    (['transferência enviada', 'kaiubi', 'easynvest'], 'Investments'),
    (['transferência enviada', 'kaiubi', 'banco c6'], 'Investments'),
    (['transferência enviada', 'kaiubi', 'caixa economica', 'cef'], 'Investments'),

    # Kaiubi Transfers RECEIVED from specific Investment Institutions
    (['transferência recebida', 'kaiubi', 'xp invest'], 'Investments'),
    (['transferência recebida', 'kaiubi', 'Banco XP S.A'], 'Investments'),
    (['transferência recebida', 'kaiubi', 'easynvest'], 'Investments'),

    (['transferência recebida', 'kaiubi', 'unibanco'], 'Income'),
    
    
    # Specific Account Transfers (New)
    (['iti *kaiubi ferrei'], 'Account Transfer'),

    # Other specific Investment institutions / transactions (New and Existing)
    (['banco topazio'], 'Investments'),
    (['remessa online'], 'Investments'),
    (['resgate fundo'], 'Investments'),
    (['aplicação rdb'], 'Investments'),
    (['resgate rdb'], 'Investments'),
    (['aplicação fundo'], 'Investments'),
    (['transferência de saldo nuinvest'], 'Investments'),
    (['saldo nuinvest'], 'Investments'),
    (['irrf sobre investimento'], 'Investments - Taxes'),

    # General Kaiubi Transfers (Fallbacks - Crucial for non-investment Kaiubi transfers like ITAU)
    (['transferência recebida', 'kaiubi'], 'Account Transfer'),
    (['transferência enviada', 'kaiubi'], 'Account Transfer'),
    (['leetcode'], 'Education - Online Learning'),

    # Financial - Loans & Specific Bank Transactions
    (['resgate de crédito pessoal'], 'Financial - Loan Related'),
    (['credito pessoal'], 'Financial - Loan Related'),
    (['depósito de crédito pessoal'], 'Financial - Loan Related'),
    (['rewards - assinatura'], 'Financial - Cashback/Rewards'),
    (['rewards assinatura'], 'Financial - Cashback/Rewards'),
    (['rewards'], 'Financial - Cashback/Rewards'),
    (['tarifa bancaria','tar-'], 'Taxes & Fees - Bank Charges'),
    (['nubank ultravioleta - mensalidade'], 'Taxes & Fees - Credit Card Charges'),
    (['saque'], 'Financial - Cash Withdrawal'),
    (['doc'], 'Financial - Bank Transfer'),
    (['transferencia doc'], 'Financial - Bank Transfer'),
    (['ted'], 'Financial - Bank Transfer'),
    (['transferencia ted'], 'Financial - Bank Transfer'),

    # Specific Payees & Unique Transactions (New and Existing)
    (['tamires rodrigues de sousa'], 'Mortgage'),
    (['tamires rodrigues de souza'], 'Mortgage'),
    (['quality imoveis sp'], 'Housing - Rent'),
    (['transferência recebida', 'pix', 'srf', 'irpf', '00.394.460/0058-87'], 'Tax Return'),
    (['secr. da receita federal'], 'Tax Return'),
    (['receita federal'], 'Tax Return'),
    (['zero berto car'], 'Car Purchase'),
    (['bruno ferreira fotog'], 'Wedding Expenses'),
    (['pepper drinks'], 'Wedding Expenses'),
    (['casa das aliancas'], 'Wedding Expenses'),
    (['casa das alianças'], 'Wedding Expenses'),
    (['vestire'], 'Wedding Expenses'),
    (['atelier pamela'], 'Wedding Expenses'),
    (['o rei dos convites comercial'], 'Wedding Expenses'),
    (['espaço favoritto buffet'], 'Wedding Expenses'),
    (['glenda carolina'], 'Wedding Expenses'),
    (['solucoees em consultoria integradas'], 'Wedding Expenses'),
    (['julio vieira'], 'Services - Piano Lessons'),
    (['sonho lar consultoria'], 'Housing - Rent'),
    (['maria josé'], 'Home Services - Maid'),
    (['quintoandar'], 'Housing - Rent'),
    (['quinto andar'], 'Housing - Rent'),
    (['amppy'], 'Home Services - Maid'),
    (['dsobral'], 'Home - Reform/Maintenance'),
    (['daniel valeriano sobral'], 'Home - Reform/Maintenance'),
    (['vitor nocelli'], 'Home - Reform/Maintenance'),
    (['argetax administracao'], 'Transport - Fuel'),
    (['argetax'], 'Transport - Fuel'),
    (['wise brasil'], 'Travel - Currency Exchange'),
    (['wise'], 'Travel - Currency Exchange'),
    (['western union'], 'Travel - Currency Exchange'),
    (['pet ltda'], 'Pets'),
    (['porto pet'], 'Pets'),
    (['medicapet'], 'Pets - Vet/Services'),
    (['animatrix'], 'Pets - Vet/Services'),


    # --- End of Highly Specific Payee/Transfer Rules ---

    # Travel (New and Existing - Grouped for clarity)
    (['hurb technologies'], 'Travel'),
    (['hurb'], 'Travel'),
    (['universal fl/lockers'], 'Travel - Theme Parks/Attractions'),
    (['aerolinea'], 'Travel - Flights'),
    (['lineas aereas'], 'Travel - Flights'),
    (['lufthan'], 'Travel - Flights'),
    (['civitatis'], 'Travel - Tours/Activities'),
    (['decolar.com'], 'Travel - Agencies'),
    (['decolar'], 'Travel - Agencies'),
    (['omio'], 'Travel - Agencies'),
    (['cvc'], 'Travel - Agencies'),
    (['faroltur'], 'Travel - Agencies'),
    (['pousada'], 'Travel - Accommodation'),
    (['hotel'], 'Travel - Accommodation'),
    (['reserva do j'], 'Travel - Accommodation'),
    (['hoteis.com'], 'Travel - Accommodation'),
    (['hoteis com'], 'Travel - Accommodation'),
    (['booking.com'], 'Travel - Accommodation'),
    (['booking'], 'Travel - Accommodation'),
    (['airbnb'], 'Travel - Accommodation'),
    (['latam airlines'], 'Travel - Flights'),
    (['latam'], 'Travel - Flights'),
    (['azul linhas'], 'Travel - Flights'),
    (['gol linhas'], 'Travel - Flights'),
    (['patagonia'], 'Travel - Tours/Activities'),
    (['kaliman'], 'Travel - Tours/Activities'),
    (['clickbus'], 'Travel - Bus'),
    (['guiche virtual'], 'Travel - Bus'),
    (['guichê virtual'], 'Travel - Bus'),
    (['souvenir'], 'Travel - Souvenirs'),
    (['taxa de visto'], 'Travel - Fees/Visas'),
    (['frango assado'], 'Travel - Roadside Stops/Restaurants'),
    (['aeropue'], 'Travel - Flights'),
    (['kuar 1900'], 'Travel - Accommodation'),
    (['newton sampaio'], 'Travel - Tours/Activities'),
    (['transferência enviada pelo pix - adrieli c dos santos'], 'Travel - Shared Expenses'),
    (['transferência enviada pelo pix - leandro xavier borges'], 'Travel - Shared Expenses'),

    # Entertainment (New and Existing - Grouped for clarity)
    (['ticketmaster'], 'Entertainment - Tickets'),
    (['tkt360'], 'Entertainment - Tickets'),
    (['steamgames.com'], 'Entertainment - Games'),
    (['steam purchase'], 'Entertainment - Games'),
    (['nuuvem'], 'Entertainment - Games'),
    (['playstation'], 'Entertainment - Games'),
    (['psn'], 'Entertainment - Games'),
    (['xbox'], 'Entertainment - Games'),
    (['microsoft store', 'xbox'], 'Entertainment - Games'),
    (['microsoft store', 'game'], 'Entertainment - Games'),
    (['pag*xsollagames'], 'Entertainment - Games'),
    (['chess.com'], 'Entertainment - Games'),
    (['epicgames'], 'Entertainment - Games'),
    (['club madame'], 'Entertainment - Bar/Nightclub'),
    (['baden baden'], 'Entertainment - Bar/Nightclub'),
    (['dj club'], 'Entertainment - Bar/Nightclub'),
    (['rock club'], 'Entertainment - Bar/Nightclub'),
    (['pier 3'], 'Entertainment - Bar/Nightclub'),
    (['arquidiocesana'], 'Entertainment - Bar/Nightclub'),
    (['adega'], 'Entertainment - Bar/Nightclub'),
    (['beer'], 'Entertainment - Bar/Nightclub'),
    (['tokyo sp'], 'Entertainment - Bar/Nightclub'),
    (['the blue pub'], 'Entertainment - Bar/Nightclub'),
    (['divvino'], 'Entertainment - Bar/Nightclub'),
    (['dica distribuidora'], 'Entertainment - Bar/Nightclub'),
    (['comedy club'], 'Entertainment - Bar/Nightclub'),
    (['comercio de bebid'], 'Entertainment - Bar/Nightclub'),
    (['vila madalen'], 'Entertainment - Bar/Nightclub'),
    (['kartodromo'], 'Entertainment - Karting'),
    (['cinema'], 'Entertainment - Movies'),
    (['cinemark'], 'Entertainment - Movies'),
    (['uci'], 'Entertainment - Movies'),
    (['kinoplex'], 'Entertainment - Movies'),
    (['cinepolis'], 'Entertainment - Movies'),
    (['ingresso.com'], 'Entertainment - Tickets'),
    (['ingresso rapido'], 'Entertainment - Tickets'),
    (['ingressorap'], 'Entertainment - Tickets'),
    (['sympla'], 'Entertainment - Tickets'),
    (['teatro'], 'Entertainment - Theatre/Shows'),
    (['osesp'], 'Entertainment - Concerts/Orchestra'),

    # Specific Online Subscriptions & Services (Existing, with new additions)
    (['obsidian.md'], 'Services - Software/Cloud'),
    (['obsidian'], 'Services - Software/Cloud'),
    (['google a medium corp'], 'Services - Online Platform'),
    (['medium corp'], 'Services - Online Platform'),
    (['twitch'], 'Services - Online Platform'),
    (['audible'], 'Services - Online Platform'),
    (['pb*samsung'], 'Services - Online Platform'),
    (['patreonirel'], 'Services - Online Platform'),
    (['google chatgpt'], 'Services - Software/Cloud'),
    (['chatgpt'], 'Services - Software/Cloud'),
    (['google cloud'], 'Services - Software/Cloud'),
    (['google evernote'], 'Services - Software/Cloud'),
    (['google storage'], 'Services - Software/Cloud'),
    (['github.com'], 'Services - Software/Cloud'),
    (['linkedin'], 'Services - Professional Subscription'),
    (['linkedin premium'], 'Services - Professional Subscription'),
    (['dashlane'], 'Services - Password Manager'),
    (['trademap'], 'Services - Financial Platforms'),
    (['mobills'], 'Services - Financial Tools'),
    (['locaweb'], 'Services - Web Hosting/Domain'),
    (['wix'], 'Services - Web Hosting/Domain'),
    (['home assistant cloud'], 'Services - Cloud Subscription'),
    (['microsoft*subscription'], 'Services - Software/Cloud'),
    (['melimais'], 'Services - Subscription Meli+'),
    (['meli+'], 'Services - Subscription Meli+'),
    (['crunchyroll'], 'Streaming'),
    (['curiositystream'], 'Streaming'),
    (['spotify'], 'Streaming'),
    (['netflix'], 'Streaming'),
    (['globoplay'], 'Streaming'),
    (['disneyplus'], 'Streaming'),
    (['disney+'], 'Streaming'),
    (['prime video'], 'Streaming'),
    (['amazon prime', 'video'], 'Streaming'),
    (['youtube', 'premium'], 'Streaming'),
    (['google youtube'], 'Streaming'),
    (['google play'], 'Streaming'),
    (['youtube'], 'Streaming'),
    (['hbo max'], 'Streaming'),
    (['hbo'], 'Streaming'),
    (['max', 'streaming'], 'Streaming'),
    (['vimeo.com'], 'Streaming'),
    (['xsolla'], 'Streaming'),
    (['dramabox'], 'Streaming'),
    (['coursera.org'], 'Education'),
    (['coursera'], 'Education'),
    (['coursra'], 'Education'),
    (['udemy'], 'Education'),
    (['musescore'], 'Education - Music Learning'),
    (['pianomarvel'], 'Education - Music Learning'),
    (['algoexpert'], 'Education - Online Learning'),
    (['sunoresearch'], 'Education - Online Learning'),
    (['stoodi'], 'Education - Online Learning'),
    (['vox2you'], 'Education'),
    (['supesprof'], 'Education'),
    (['courses'], 'Education'),
    (['cursochurras'], 'Education - Courses'),
    (['steamgames.com'], 'Entertainment - Games'),
    (['steam purchase'], 'Entertainment - Games'),
    (['nuuvem'], 'Entertainment - Games'),
    (['playstation'], 'Entertainment - Games'),
    (['psn'], 'Entertainment - Games'),
    (['xbox'], 'Entertainment - Games'),
    (['microsoft store', 'xbox'], 'Entertainment - Games'),
    (['microsoft store', 'game'], 'Entertainment - Games'),

    # Online Marketplaces & General Online Purchases
    (['mercadolivre'], 'Online Purchases'),
    (['mclivre'], 'Online Purchases'),
    (['amazon.com.br'], 'Online Purchases'),
    (['amazon marketplace'], 'Online Purchases'),
    (['amazon'], 'Online Purchases'),
    (['shopee'], 'Online Purchases'),
    (['shein'], 'Online Purchases'),
    (['aliexpress'], 'Online Purchases'),
    (['ebay'], 'Online Purchases'),
    (['alipaybrasil'], 'Online Purchases'),
    (['alipay'], 'Online Purchases'),
    (['wish.com'], 'Online Purchases'),
    (['dx.com'], 'Online Purchases'),
    (['americanas'], 'Online Purchases'),
    (['submarino'], 'Online Purchases'),
    (['kabum'], 'Online Purchases'),
    (['magazine'], 'Online Purchases'),
    (['magalu'], 'Online Purchases'),
    (['dell'], 'Online Purchases - Electronics'),
    (['dafiti'], 'Online Purchases'),
    (['extra.com'], 'Online Purchases'),
    (['google play', 'google store'], 'Online Purchases - Digital Content'),

    # Food & Dining
    (['degustaeventos'], 'Food & Dining - Event'),
    (['taste sao paulo'], 'Food & Dining - Event'),
    (['fiorella'], 'Food & Dining - Bakery'),
    (['panificadora'], 'Food & Dining - Bakery'),
    (['grao do ipiranga'], 'Food & Dining - Bakery'),
    (['pao do parque'], 'Food & Dining - Bakery'),
    (['paes'], 'Food & Dining - Bakery'),
    (['la terrazza'], 'Food & Dining - Restaurant'),
    (['pata negra'], 'Food & Dining - Restaurant'),
    (['underdog'], 'Food & Dining - Restaurant'),
    (['pizza'], 'Food & Dining - Restaurant'),
    (['tempero de casa'], 'Food & Dining - Restaurant'),
    (['espeto'], 'Food & Dining - Restaurant'),
    (['cozinha'], 'Food & Dining - Restaurant'),
    (['dona marla'], 'Food & Dining - Restaurant'),
    (['churrasco'], 'Food & Dining - Restaurant'),
    (['madero'], 'Food & Dining - Restaurant'),
    (['santo dica'], 'Food & Dining - Restaurant'),
    (['feijao'], 'Food & Dining - Restaurant'),
    (['bella napoli'], 'Food & Dining - Restaurant'),
    (['arturito'], 'Food & Dining - Restaurant'),
    (['sushi'], 'Food & Dining - Restaurant'),
    (['hard rock cafe'], 'Food & Dining - Restaurant'),
    (['tratto'], 'Food & Dining - Restaurant'),
    (['serradomar'], 'Food & Dining - Restaurant'),
    (['taverna'], 'Food & Dining - Restaurant'),
    (['peixada'], 'Food & Dining - Restaurant'),
    (['chicken'], 'Food & Dining - Restaurant'),
    (['a casa do porco'], 'Food & Dining - Restaurant'),
    (['trem bom de minas'], 'Food & Dining - Restaurant'),
    (['vassoura quebrad'], 'Food & Dining - Restaurant'),
    (['dibaco'], 'Food & Dining - Restaurant'),
    (['villa grano'], 'Food & Dining - Restaurant'),
    (['abbraccio'], 'Food & Dining - Restaurant'),
    (['terraco'], 'Food & Dining - Restaurant'),
    (['waffle'], 'Food & Dining - Restaurant'),
    (['rest japones'], 'Food & Dining - Restaurant'),
    (['coco bambu'], 'Food & Dining - Restaurant'),
    (['garage sp'], 'Food & Dining - Restaurant'),
    (['marmitaria'], 'Food & Dining - Delivery'),
    (['cantinho mineiro'], 'Food & Dining - Restaurant'),
    (['ifood'], 'Food & Dining - Delivery'),
    (['ifd*'], 'Food & Dining - Delivery'),
    (['rappi'], 'Food & Dining - Delivery'),
    (['liv up'], 'Food & Dining - Delivery'),
    (['ze delivery'], 'Food & Dining - Delivery'),
    (['zé delivery'], 'Food & Dining - Delivery'),
    (['mcdonalds'], 'Food & Dining - Fast Food'),
    (['mc donalds'], 'Food & Dining - Fast Food'),
    (['burger king'], 'Food & Dining - Fast Food'),
    (['bk'], 'Food & Dining - Fast Food'),
    (['burger'], 'Food & Dining - Fast Food'),
    (['hamburgueria'], 'Food & Dining - Fast Food'),
    (['habibs'], 'Food & Dining - Fast Food'),
    (["habib's"], 'Food & Dining - Fast Food'),
    (['outback'], 'Food & Dining - Restaurant'),
    (['r.c carbonell'], 'Food & Dining - Restaurant'),
    (['pag*icekombi'], 'Food & Dining - Restaurant'),
    (['petitartur'], 'Food & Dining - Restaurant'),
    (['petit artur'], 'Food & Dining - Restaurant'),
    (['si senor'], 'Food & Dining - Restaurant'),
    (['quiosque'], 'Food & Dining - Restaurant'),
    (['las chicas'], 'Food & Dining - Restaurant'),
    (['gastronomia'], 'Food & Dining - Restaurant'),
    (['emporio'], 'Food & Dining - Restaurant'),
    (['parrilla'], 'Food & Dining - Restaurant'),
    (['baccio'], 'Food & Dining - Ice Cream'),
    (['bacio di latte'], 'Food & Dining - Ice Cream'),
    (['sorvetes'], 'Food & Dining - Ice Cream'),
    (['sorvete'], 'Food & Dining - Ice Cream'),
    (['ice kombi'], 'Food & Dining - Ice Cream'),
    (['cuor di crema'], 'Food & Dining - Ice Cream'),
    (['starbucks'], 'Food & Dining - Cafe'),
    (['pastel'], 'Food & Dining - Snacks/Misc'),
    (['pasteis'], 'Food & Dining - Snacks/Misc'),
    (['salgados'], 'Food & Dining - Snacks/Misc'),
    (['acaraje'], 'Food & Dining - Snacks/Misc'),
    (['lanchonete'], 'Food & Dining - Snacks/Misc'),
    (['esfiha'], 'Food & Dining - Snacks/Misc'),
    (['coffee'], 'Food & Dining - Cafe'),
    (['coffe'], 'Food & Dining - Cafe'),
    (['cafe', 'lanche'], 'Food & Dining - Cafe'),
    (['padaria'], 'Food & Dining - Bakery'),
    (['pan. e conf.'], 'Food & Dining - Bakery'),
    (['restaurante'], 'Food & Dining - Restaurant'),
    (['restaurant'], 'Food & Dining - Restaurant'),
    (['food'], 'Food & Dining - Restaurant'),
    (['alimentacao'], 'Food & Dining - Restaurant'),
    (['alimentos'], 'Food & Dining - Restaurant'),
    (['bem alimentacao'], 'Food & Dining - Restaurant'),
    (['doces'], 'Food & Dining - Snacks/Misc'),
    (['cafeteria'], 'Food & Dining - Cafe'),
    (['bar'], 'Food & Dining - Restaurant'),

    # Groceries / Supermarket
    (['vila das frutas'], 'Groceries'),
    (['peixaria'], 'Groceries'),
    (['minuto pa'], 'Groceries'),
    (['minuto pao de acucar'], 'Groceries'),
    (['minuto pão de açúcar'], 'Groceries'),
    (['da santa'], 'Groceries'),
    (['hortifruti da santa'], 'Groceries'),
    (['extra jaguare'], 'Groceries'),
    (['extra jaguaré'], 'Groceries'),
    (['cleumildes'], 'Groceries'),
    (['smart break'], 'Groceries'),
    (['inovakamura'], 'Groceries'),
    (['frutas'], 'Groceries'),
    (['frutaria'], 'Groceries'),
    (['inovasanchez'], 'Groceries'),
    (['dia brasil'], 'Groceries'),
    (['supermercado'], 'Groceries'),
    (['mercado'], 'Groceries'),
    (['beef'], 'Groceries'),
    (['carne'], 'Groceries'),
    (['beef boutique'], 'Groceries'),
    (['extra hiper'], 'Groceries'),
    (['carrefour'], 'Groceries'),
    (['pao de acucar'], 'Groceries'),
    (['pão de açúcar'], 'Groceries'),
    (['assai'], 'Groceries'),
    (['assaí'], 'Groceries'),
    (['atacadao'], 'Groceries'),
    (['atacadão'], 'Groceries'),
    (['sams club'], 'Groceries'),
    (["sam's club"], 'Groceries'),
    (['acougue'], 'Groceries'),
    (['açougue'], 'Groceries'),
    (['pag*comercialde'], 'Groceries'),
    (['hirota'], 'Groceries'),
    (['wal mart'], 'Groceries'),
    (['walmart'], 'Groceries'),
    (['bom beef'], 'Groceries'),
    (['meet and fire'], 'Groceries'),
    (['shopper'], 'Groceries'),
    (['carnes'], 'Groceries'),
    (['anaguma comercio de al'], 'Groceries'),
    (['mini extra'], 'Groceries'),
    (['bauducco'], 'Groceries'),
    (['pescado'], 'Groceries'),
    (['swift'], 'Groceries'),
    (['swfit'], 'Groceries'),
    (['tolezano'], 'Groceries'),
    (['comercio de alime'], 'Groceries'),
    (['superm'], 'Groceries'),
    (['soberano festas'], 'Groceries'),
    (['varejista'], 'Groceries'),
    (['comercio de verdur'], 'Groceries'),
    (['oxxo'], 'Groceries'),


    # Transport
    (['localiza'], 'Transport - Car Rental'),
    (['movida'], 'Transport - Car Rental'),
    (['unidas', 'aluguel de carros'], 'Transport - Car Rental'),
    (['rentalcars'], 'Transport - Car Rental'),
    (['aluguel de carros'], 'Transport - Car Rental'),
    (['uber'], 'Transport - App'),
    (['99app'], 'Transport - App'),
    (['99 taxi'], 'Transport - App'),
    (['cabify'], 'Transport - App'),
    (['nutag'], 'Transport - Tolls'),
    (['nu tag'], 'Transport - Tolls'),
    (['sem parar'], 'Transport - Tolls'),
    (['conectcar'], 'Transport - Tolls'),
    (['veloe'], 'Transport - Tolls'),
    (['bilhete unico'], 'Transport - Public Transit'),
    (['cartao top', 'cartão top'], 'Transport - Public Transit'),
    (['vamu'], 'Transport - Public Transit'),
    (['bilh unico'], 'Transport - Public Transit'),
    (['shellbox'], 'Transport - Fuel'),
    (['shell box'], 'Transport - Fuel'),
    (['ipiranga', 'combustivel'], 'Transport - Fuel'),
    (['abastece ai'], 'Transport - Fuel'),
    (['posto ipiranga'], 'Transport - Fuel'),
    (['petrobras'], 'Transport - Fuel'),
    (['posto br'], 'Transport - Fuel'),
    (['rede campeao'], 'Transport - Fuel'),
    (['posto'], 'Transport - Fuel'),
    (['pag*jaguare'], 'Transport - Fuel'),
    (['estacionament'], 'Transport - Parking'),
    (['estapar'], 'Transport - Parking'),
    (['mono nubank'], 'Transport - Parking'),
    (['tsusho'], 'Transport - Car Maintenance'),
    (['centro automotivo'], 'Transport - Car Maintenance'),
    (['allpark'], 'Transport - Parking'),
    (['multiplan administrado'], 'Transport - Parking'),
    (['multiplan'], 'Transport - Parking'),
    (['sao bernardo plaza'], 'Transport - Parking'),
    (['são bernardo plaza'], 'Transport - Parking'),
    (['park'], 'Transport - Parking'),
    (['principe humberto esta'], 'Transport - Parking'),
    (['shopping'], 'Transport - Parking'),
    (['marco zero'], 'Transport - Parking'),
    (['indigo'], 'Transport - Parking'),
    (['golden square'], 'Transport - Parking'),
    (['estaciona'], 'Transport - Parking'),
    (['andreense motos'], 'Transport - Car Maintenance'),
    (['motorcycles'], 'Transport - Car Maintenance'),
    (['propig *auto relampago'], 'Transport - Car Maintenance'),
    (['auto relampago'], 'Transport - Car Maintenance'),
    (['moto pecas'], 'Transport - Car Maintenance'),
    (['lava rapido'], 'Transport - Car Wash'),
    (['auto post'], 'Transport - Fuel'),
    (['via independencia'], 'Transport - Fuel'),

    # Utilities
    (['conta vivo'], 'Utilities - Phone/Internet'),
    (['vivo'], 'Utilities - Phone/Internet'),
    (['claro'], 'Utilities - Phone/Internet'),
    (['net servicos'], 'Utilities - Phone/Internet'),
    (['telefonica brasil'], 'Utilities - Phone/Internet'),
    (['enelsp'], 'Utilities - Electricity'),
    (['enel'], 'Utilities - Electricity'),
    (['light'], 'Utilities - Electricity'),
    (['cpfl'], 'Utilities - Electricity'),
    (['sabesp'], 'Utilities - Water'),
    (['comgas'], 'Utilities - Gas'),
    (['comgás'], 'Utilities - Gas'),

    # Health & Wellness
    (['droga raia'], 'Health - Pharmacy'),
    (['drogaraia'], 'Health - Pharmacy'),
    (['raia'], 'Health - Pharmacy'),
    (['drogasil'], 'Health - Pharmacy'),
    (['pague menos'], 'Health - Pharmacy'),
    (['ultrafarma'], 'Health - Pharmacy'),
    (['drogaria são paulo'], 'Health - Pharmacy'),
    (['drogaria sao paulo'], 'Health - Pharmacy'),
    (['drogarias pacheco'], 'Health - Pharmacy'),
    (['panvel'], 'Health - Pharmacy'),
    (['farmacia', 'popular'], 'Health - Pharmacy'),
    (['farmacia'], 'Health - Pharmacy'),
    (['drogaria'], 'Health - Pharmacy'),
    (['farma'], 'Health - Pharmacy'),
    (['drog'], 'Health - Pharmacy'),
    (['dragaria'], 'Health - Pharmacy'),
    (['amil'], 'Health - Insurance'),
    (['unimed'], 'Health - Insurance'),
    (['bradesco saude'], 'Health - Insurance'),
    (['sulamerica saude'], 'Health - Insurance'),
    (['sulamérica saúde'], 'Health - Insurance'),
    (['clinica'], 'Health - Clinic/Consultation'),
    (['medicos'], 'Health - Clinic/Consultation'),
    (['consultoria medica'], 'Health - Clinic/Consultation'),
    (['smart fit'], 'Health - Gym'),
    (['smartfit'], 'Health - Gym'),
    (['bodytech'], 'Health - Gym'),
    (['bio ritmo'], 'Health - Gym'),
    (['aqua schoolac'], 'Health - Gym'),
    (['gympass'], 'Health - Gym'),
    (['wellhub'], 'Health - Gym'),
    (['academia'], 'Health - Gym'),
    (['crossfit'], 'Health - Gym'),
    (['freeletics'], 'Health - Gym'),
    (['bluefit'], 'Health - Gym'),
    (['redfit'], 'Health - Gym'),
    (['fitness22'], 'Health - Gym'),
    (['sanmer'], 'Health - Gym'),
    (['fleury'], 'Health - Labs/Diagnostics'),
    (['lavoisier'], 'Health - Labs/Diagnostics'),
    (['delboni auriemo', 'delboni'], 'Health - Labs/Diagnostics'),
    (['odontoclinic'], 'Health - Dental'),
    (['sorridents'], 'Health - Dental'),
    (['remedio'], 'Health - Pharmacy'),
    (['suplemento'], 'Health - Supplements'),

    # Pets
    (['melhorqgente'], 'Pets'),
    (['melhor q gente'], 'Pets'),
    (['petz'], 'Pets'),
    (['cobasi'], 'Pets'),
    (['petlove'], 'Pets'),
    (['veterinario', 'veterinaria'], 'Pets - Vet/Services'),
    (['banho e tosa', 'pet shop banho'], 'Pets - Vet/Services'),
    (['hitpaw'], 'Streaming'),
    (['health for pet'], 'Pets - Vet/Services'),
    (['pets'], 'Pets'),
    (['pet center'], 'Pets'),
    (['camarim da casa'], 'Shopping - Home Decor/Furniture'),
    (['nothingprojector'], 'Shopping - Home Decor/Furniture'),
    (['geniodesk'], 'Shopping - Home Decor/Furniture'),
    (['quadros e cia'], 'Shopping - Home Decor/Furniture'),
    (['madeiramadeir'], 'Shopping - Home Decor/Furniture'),
    (['panela de fe'], 'Shopping - Home Decor/Furniture'),
    (['artes'], 'Shopping - Home Decor/Furniture'),
    (['decoracao'], 'Shopping - Home Decor/Furniture'),
    (['sylvia design'], 'Shopping - Home Decor/Furniture'),
    (['vitrais'], 'Shopping - Home Decor/Furniture'),
    (['comfort center'], 'Shopping - Home Decor/Furniture'),
    (['daiso'], 'Shopping - Variety Store'),
    (['imaginarium'], 'Shopping - Gifts/Misc'),
    (['giuliana flores'], 'Shopping - Gifts/Flowers'),
    (['puket'], 'Shopping - Gifts/Misc'),
    (['buddha spa'], 'Shopping - Gifts/Misc'),
    (['brinquedos'], 'Shopping - Toys'),
    (['ar condicionado', 'compra'], 'Shopping - Electronics/Home'),
    (['ar condicionado', 'instalacao', 'instalação'], 'Home - Reform/Maintenance'),
    (['ar condicionado', 'manutencao', 'manutenção'], 'Home - Reform/Maintenance'),
    (['ar condicionado'], 'Home - Reform/Maintenance'),
    (['tok&stok'], 'Shopping - Home Decor/Furniture'),
    (['tok stok'], 'Shopping - Home Decor/Furniture'),
    (['etna'], 'Shopping - Home Decor/Furniture'),
    (['camicado'], 'Shopping - Home Decor/Furniture'),
    (['c&a'], 'Shopping - Clothing'),
    (['c&a modas'], 'Shopping - Clothing'),
    (['cea pay'], 'Shopping - Clothing'),
    (['renner'], 'Shopping - Clothing'),
    (['lojas renner'], 'Shopping - Clothing'),
    (['riachuelo'], 'Shopping - Clothing'),
    (['zara'], 'Shopping - Clothing'),
    (['via veneto'], 'Shopping - Clothing'),
    (['polo'], 'Shopping - Clothing'),
    (['planet girls'], 'Shopping - Clothing'),
    (['decathlon'], 'Shopping - Sporting Goods'),
    (['centauro'], 'Shopping - Sporting Goods'),
    (['youcom'], 'Shopping - Clothing'),
    (['lhetashop'], 'Shopping - Clothing'),
    (['cea scs'], 'Shopping - Clothing'),
    (['galeriadorock'], 'Shopping - Clothing'),
    (['fashion'], 'Shopping - Clothing'),
    (['fatto a mano'], 'Shopping - Clothing'),
    (['khelf'], 'Shopping - Clothing'),
    (['dudalina'], 'Shopping - Clothing'),
    (['bayard esportes'], 'Shopping - Clothing'),
    (['calcados'], 'Shopping - Shoes'),
    (['instrumentos'], 'Shopping - Music Instruments'),
    (['le postiche'], 'Shopping - Bags/Luggage'),
    (['mens market'], 'Shopping - Personal Care'),
    (['cosmeticos'], 'Shopping - Personal Care'),
    (['loccitane'], 'Shopping - Personal Care'),
    (['bestgo'], 'Shopping - Electronics/Accessories'),
    (['otica solarium'], 'Shopping - Eyewear'),
    (['leroy merlin'], 'Shopping - Home Improvement'),
    (['telhanorte'], 'Shopping - Home Improvement'),
    (['telha norte'], 'Shopping - Home Improvement'),
    (['sodimac'], 'Shopping - Home Improvement'),
    (['c&c casa e construcao', 'c&c', 'cec'], 'Shopping - Home Improvement'),
    (['casa e construcao'], 'Shopping - Home Improvement'),
    (['material de construcao', 'material construcao'], 'Shopping - Home Improvement'),
    (['materiais de construc'], 'Shopping - Home Improvement'),
    (['casa da eletrica'], 'Shopping - Home Improvement'),
    (['casa do led'], 'Shopping - Home Improvement'),
    (['construdecor'], 'Shopping - Home Improvement'),
    (['livraria cultura'], 'Shopping - Books'),
    (['saraiva'], 'Shopping - Books'),
    (['ri happy'], 'Shopping - Toys'),
    (['pbkids'], 'Shopping - Toys'),
    (['le biscuit'], 'Shopping - Variety Store'),
    (['nothingprojector'], 'Shopping - Home Decor/Furniture'),
    (['geniodesk'], 'Shopping - Home Decor/Furniture'),
    (['youcom'], 'Shopping - Clothing'),
    (['lhetashop'], 'Shopping - Clothing'),
    (['quadros e cia'], 'Shopping - Home Decor/Furniture'),
    (['madeiramadeir'], 'Shopping - Home Decor/Furniture'),
    (['panela de fe'], 'Shopping - Home Decor/Furniture'),
    (['artes'], 'Shopping - Home Decor/Furniture'),
    (['decoracao'], 'Shopping - Home Decor/Furniture'),
    (['sylvia design'], 'Shopping - Home Decor/Furniture'),
    (['imaginarium'], 'Shopping - Gifts/Misc'),
    (['giuliana flores'], 'Shopping - Gifts/Flowers'),
    (['puket'], 'Shopping - Gifts/Misc'),
    (['ar condicionado', 'compra'], 'Shopping - Electronics/Home'),
    (['ar condicionado', 'instalacao', 'instalação'], 'Home - Reform/Maintenance'),
    (['ar condicionado', 'manutencao', 'manutenção'], 'Home - Reform/Maintenance'),
    (['ar condicionado'], 'Home - Reform/Maintenance'),
    (['tok&stok'], 'Shopping - Home Decor/Furniture'),
    (['tok stok'], 'Shopping - Home Decor/Furniture'),
    (['etna'], 'Shopping - Home Decor/Furniture'),
    (['camicado'], 'Shopping - Home Decor/Furniture'),
    (['c&a'], 'Shopping - Clothing'),
    (['c&a modas'], 'Shopping - Clothing'),
    (['cea pay'], 'Shopping - Clothing'),
    (['renner'], 'Shopping - Clothing'),
    (['lojas renner'], 'Shopping - Clothing'),
    (['riachuelo'], 'Shopping - Clothing'),
    (['zara'], 'Shopping - Clothing'),
    (['via veneto'], 'Shopping - Clothing'),
    (['polo'], 'Shopping - Clothing'),
    (['planet girls'], 'Shopping - Clothing'),
    (['decathlon'], 'Shopping - Sporting Goods'),
    (['centauro'], 'Shopping - Sporting Goods'),
    (['youcom'], 'Shopping - Clothing'),
    (['lhetashop'], 'Shopping - Clothing'),
    (['cea scs'], 'Shopping - Clothing'),
    (['galeriadorock'], 'Shopping - Clothing'),
    (['fashion'], 'Shopping - Clothing'),
    (['fatto a mano'], 'Shopping - Clothing'),
    (['khelf'], 'Shopping - Clothing'),
    (['dudalina'], 'Shopping - Clothing'),
    (['calcados'], 'Shopping - Shoes'),
    (['instrumentos'], 'Shopping - Music Instruments'),
    (['le postiche'], 'Shopping - Bags/Luggage'),
    (['mens market'], 'Shopping - Personal Care'),
    (['cosmeticos'], 'Shopping - Personal Care'),
    (['loccitane'], 'Shopping - Personal Care'),
    (['bestgo'], 'Shopping - Electronics/Accessories'),
    (['otica solarium'], 'Shopping - Eyewear'),
    (['mobills'], 'Services - Financial Tools'),
    (['locaweb'], 'Services - Web Hosting/Domain'),
    (['wix'], 'Services - Web Hosting/Domain'),
    (['melimais'], 'Services - Subscription Meli+'),
    (['meli+'], 'Services - Subscription Meli+'),
    (['studio'], 'Services - Barber'),

    # Insurance (Non-Health)
    (['tokio marine'], 'Insurance - General'),
    (['porto seguro'], 'Insurance - General'),
    (['bb seguros'], 'Insurance - General'),
    (['mapfre'], 'Insurance - General'),
    (['nu seguro celular'], 'Insurance'),
    (['seguro celular'], 'Insurance'),
    (['celular seguro'], 'Insurance'),
    (['manicure', 'pedicure'], 'Services - Beauty/Salon'),
    (['refugio do nobre'], 'Services - Barber'),
    (['refugio do n'], 'Services - Barber'),
    (['studio plaza prime'], 'Services - Barber'),
    (['studio'], 'Services - Barber'),
    (['seguro auto'], 'Insurance - Auto'),

    # User-added rules (newly added section or append to existing logical group)
    (['auto post'], 'Transport - Fuel'),
    (['nu cafe'], 'Food & Dining - Restaurant'),
    (['valet'], 'Transport - Parking'),
    (['anchieta grill'], 'Food & Dining - Restaurant'),
    (['deposito do paraiba'], 'Home - Reform/Maintenance'),
    (['google ellation'], 'Services - Online Platform'),
    (['pix', 'aline maria souza da paz'], 'Home Services - Maid'),
    (['openai'], 'Services - Software/Cloud'),


    # Generic terms (lower priority - ensure these are LAST or near last within their logical groups)
    (['compra'], 'Online Purchases'),
    (['pagamento'], 'Services - Payments'),
    (['pgto'], 'Services - Payments'),
    (['pagto'], 'Services - Payments'),
    (['iof'], 'Taxes & Fees'),
    (['supermercado'], 'Groceries'),
    (['google ellation'], 'Services - Online Platform'),
    (['pix', 'aline maria souza da paz'], 'Home Services - Maid'),
    (['openai'], 'Services - Software/Cloud'),
    (['authentic feet'], 'Shopping - Clothing'),
    (['vestuario'], 'Shopping - Clothing'),
    (['gamestation'], 'Entertainment - Games'),
    (['du chapeu'], 'Shopping - Home Decor/Furniture'),
    (['kalunga'], 'Online Purchases'),
    (['antonio soares da silva'], 'Shopping - Home Decor/Furniture'),
    (['leandro kley'], 'Transport - Car Accident/Repair'),
    (['dreamcomfort'], 'Shopping - Home Decor/Furniture'),
    (['gabrielle leithold'], 'Wedding Expenses'),
    (['k rcher loja'], 'Shopping - Home Decor/Furniture'),
    (['inusual'], 'Shopping - Home Decor/Furniture'),
]

def _correct_ofx_char_encoding(text: str) -> str:
    """
    Attempts to correct a common character encoding issue found in OFX files
    where text intended as UTF-8 (e.g., "Crédito") is misinterpreted due to
    an incorrect 'cp1252' (Windows-1252) decoding, resulting in mojibake
    (e.g., "CrÃ©dito").
    """
    if not text:
        return text
    try:
        original_utf8_bytes = text.encode('cp1252')
        corrected_text = original_utf8_bytes.decode('utf-8')
        if corrected_text != text and 'Ã' in text and 'Ã' not in corrected_text:
            return corrected_text
        return text
    except UnicodeEncodeError:
        return text
    except UnicodeDecodeError:
        return text
    except Exception:
        return text

def parse_ofx_to_dataframe(file_path: str) -> pd.DataFrame:
    """
    Parses an OFX file and converts its transactions into a Pandas DataFrame.
    Original columns: 'id', 'date', 'type', 'amount', 'memo'.
    """
    expected_columns = [COLUMN_ID, COLUMN_DATE, COLUMN_TYPE, COLUMN_AMOUNT, COLUMN_MEMO]
    try:
        with open(file_path, 'rb') as f:
            ofx = OfxParser.parse(f)
    except FileNotFoundError:
        print(f"Error: File not found at {file_path}")
        return pd.DataFrame(columns=expected_columns)
    except Exception as e:
        print(f"Error parsing OFX file {file_path}: {e}")
        return pd.DataFrame(columns=expected_columns)

    transactions_list = []

    if ofx.account is None:
        print(f"Warning: No account information found in {file_path}.")
        return pd.DataFrame(columns=expected_columns)

    if ofx.account.statement is None:
        print(f"Warning: No statement found for account {ofx.account.account_id if hasattr(ofx.account, 'account_id') else 'N/A'} in {file_path}.")
        return pd.DataFrame(columns=expected_columns)

    if not ofx.account.statement.transactions:
        print(f"Warning: No transactions found in statement for account {ofx.account.account_id if hasattr(ofx.account, 'account_id') else 'N/A'} in {file_path}.")
        return pd.DataFrame(columns=expected_columns)

    for transaction in ofx.account.statement.transactions:
        transactions_list.append({
            COLUMN_ID: transaction.id,
            COLUMN_DATE: transaction.date,
            COLUMN_TYPE: transaction.type,
            COLUMN_AMOUNT: transaction.amount,
            COLUMN_MEMO: _correct_ofx_char_encoding(transaction.memo)
        })

    if not transactions_list:
        return pd.DataFrame(columns=expected_columns)

    df = pd.DataFrame(transactions_list)
    df[COLUMN_DATE] = pd.to_datetime(df[COLUMN_DATE]).dt.normalize()
    df[COLUMN_AMOUNT] = df[COLUMN_AMOUNT].astype(float)
    df[COLUMN_AMOUNT] = abs(df[COLUMN_AMOUNT])
    df = df[expected_columns] # Ensure defined column order before adding new ones
    return df

def process_all_ofx_files(base_dir: str) -> pd.DataFrame:
    """
    Processes all OFX files in specified subdirectories ('credit_card', 'nuconta')
    of the base_dir, adds an 'account_type' column, and concatenates them.
    """
    all_dfs = []
    
    # Define account types and their corresponding directories
    account_type_map = {
        'Credit Card': os.path.join(base_dir, 'credit_card'),
         'Nuconta': os.path.join(base_dir, 'nuconta')
    }

    for acc_type, acc_dir_path in account_type_map.items():
        if not os.path.isdir(acc_dir_path):
            print(f"Warning: Directory not found: {acc_dir_path}")
            continue
            
        ofx_files = glob.glob(os.path.join(acc_dir_path, '*.ofx'))
        if not ofx_files:
            print(f"No OFX files found in {acc_dir_path}")
            
        for file_path in ofx_files:
            print(f"Processing {acc_type} file: {file_path}")
            df = parse_ofx_to_dataframe(file_path)
            if not df.empty:
                df[COLUMN_ACCOUNT_TYPE] = acc_type
                all_dfs.append(df)
            else:
                print(f"Warning: No data parsed from {file_path}")

    if not all_dfs:
        print("No OFX files processed or no data found in any OFX file.")
        # Return an empty DataFrame with all expected columns including the new one
        final_columns = [COLUMN_ID, COLUMN_DATE, COLUMN_TYPE, COLUMN_AMOUNT, COLUMN_MEMO, COLUMN_ACCOUNT_TYPE]
        return pd.DataFrame(columns=final_columns)

    combined_df = pd.concat(all_dfs, ignore_index=True)
    return combined_df

def categorize_transactions(df: pd.DataFrame) -> pd.DataFrame:
    """
    Adds a 'category' column to the DataFrame based on transaction memos.
    Uses the global CATEGORIZATION_RULES list.
    """
    if COLUMN_MEMO not in df.columns:
        print(f"Warning: Memo column ('{COLUMN_MEMO}') not found. Cannot categorize.")
        df[COLUMN_CATEGORY] = 'Error - No Memo'
        return df

    df[COLUMN_CATEGORY] = 'Uncategorized' # Default category

    for index, row in df.iterrows():
        memo = str(row[COLUMN_MEMO]).lower() # Ensure memo is string and lowercase
        if not memo or pd.isna(row[COLUMN_MEMO]):
            continue # Skip empty or NaN memos

        for keywords, category_name in CATEGORIZATION_RULES:
            all_keywords_found = True
            for keyword in keywords:
                if keyword.lower() not in memo:
                    all_keywords_found = False
                    break
            
            if all_keywords_found:
                df.loc[index, COLUMN_CATEGORY] = category_name
                break # Move to the next transaction once categorized
    return df

if __name__ == '__main__':
    workspace_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) if "__file__" in locals() else "." 
    current_path = os.path.abspath(".")
    if os.path.basename(current_path) == "src":
        project_root_path = os.path.dirname(current_path)
    else:
        project_root_path = current_path # Assume current dir is project root

    resources_base_path = os.path.join(project_root_path, 'resources', 'files')

    print(f"Looking for OFX files in subdirectories of: {resources_base_path}")

    if not os.path.isdir(resources_base_path):
        print(f"Error: Base directory for OFX files not found: {resources_base_path}")
        print("Please ensure the 'resources/files' directory exists at the project root or adjust path.")
    else:
        combined_transactions_df = process_all_ofx_files(resources_base_path)

        if not combined_transactions_df.empty:
            print("\n--- Combined Transactions DataFrame (Before Categorization) ---")
            print(f"Shape: {combined_transactions_df.shape}")
            # print("\nInfo:")
            # combined_transactions_df.info()
            # print("\nHead:")
            # print(combined_transactions_df.head())

            # Categorize transactions
            print("\nCategorizing transactions...")
            categorized_df = categorize_transactions(combined_transactions_df.copy()) # Use .copy() to avoid SettingWithCopyWarning

            print("\n--- Categorized Transactions DataFrame (All Categories) ---")
            if categorized_df.empty:
                print(f"No transactions found or DataFrame is empty after categorization.")
            else:
                print(f"Shape: {categorized_df.shape}")
                print("\nInfo:")
                categorized_df.info()
                print("\nHead (with categories):")
                print(categorized_df[[COLUMN_MEMO, COLUMN_CATEGORY]].head())
                print("\nTail (with categories):")
                print(categorized_df[[COLUMN_MEMO, COLUMN_CATEGORY]].tail())
                
                print(f"\nAccount types found: {categorized_df[COLUMN_ACCOUNT_TYPE].unique().tolist()}")
                print("\nValue counts for 'account_type':")
                print(categorized_df[COLUMN_ACCOUNT_TYPE].value_counts())

                print("\nValue counts for 'category':")
                print(categorized_df[COLUMN_CATEGORY].value_counts().sort_index())

                uncategorized_count = (categorized_df[COLUMN_CATEGORY] == 'Uncategorized').sum()
                total_transactions = len(categorized_df)
                if total_transactions > 0:
                    percent_uncategorized = (uncategorized_count / total_transactions) * 100
                    print(f"\nNumber of Uncategorized transactions: {uncategorized_count} ({percent_uncategorized:.2f}% of total)")
                    if uncategorized_count > 0 and uncategorized_count < 20: # Print some uncategorized memos if not too many
                        print("\nSample Uncategorized Memos:")
                        print(categorized_df[categorized_df[COLUMN_CATEGORY] == 'Uncategorized'][COLUMN_MEMO].head(10).to_list())
                
                # Total amount of transactions (will be for the filtered category if filter is active)
                print(f"\nTotal amount of all transactions:")
                print(categorized_df[COLUMN_AMOUNT].sum())
                
                # Total amount of transactions by account type (for the filtered category)
                print(f"\nTotal amount by account type (all categories):")
                print(categorized_df.groupby(COLUMN_ACCOUNT_TYPE)[COLUMN_AMOUNT].sum())
                
                # Total amount by category (will be just the one category if filtered)
                print(f"\nTotal amount by category (all categories):")
                print(categorized_df.groupby(COLUMN_CATEGORY)[COLUMN_AMOUNT].sum().sort_values(ascending=False))

        else:
            print("\nNo transactions were processed from any OFX files.") 