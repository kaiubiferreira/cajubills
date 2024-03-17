import pathlib

RESOURCES_PATH = pathlib.Path().absolute().joinpath('backend/resources')
CREDIT_CARD_OFX_PATH = RESOURCES_PATH.joinpath('credit_card')
NUCONTA_OFX_PATH = RESOURCES_PATH.joinpath('nuconta')
CATEGORIES_PATH = RESOURCES_PATH.joinpath('categories.csv')
