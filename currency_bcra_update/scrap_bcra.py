from odoo import models, fields, api
from odoo.exceptions import Warning, ValidationError
import logging
import requests
from bs4 import BeautifulSoup as bs
from datetime import datetime

_logger = logging.getLogger(__name__)


class ScrapBCRA(models.TransientModel):
    _name = "bcra.scrap"
    _description = "Scrapper BCRA"

    @api.model
    def get_last_rate(self):
        ars_currency = self.env.ref('base.ARS')
        rate = self.env['res.currency.rate'].search([
            ('currency_id', '=', ars_currency.id,)
        ], limit=1, order='create_date desc')
        return {
            "rate": rate.rate,
            "date": rate.name
        }

    @api.model
    def update_rates(self):
        data = False
        count = 0
        try:
            while not data and count < 3:
                count += 1
                data = requests.get('https://www.bcra.gob.ar/')
                if data.status_code == 200:
                    soup = bs(data.text, 'html.parser')
                    ars_currency = self.env.ref('base.ARS')
                    td_list = soup.select('.table-ppales-vbles')[0].findAll('tr')[9].findAll("td")
                    fecha_bcra = False
                    try:
                        fecha_bcra = datetime.strptime(td_list[0].text[-10:], '%d/%m/%Y')
                    except Exception as e:
                        fecha_bcra = False
                    valor = td_list[1].findAll("div")[0].text.replace(',', '.')

                    self.env['res.currency.rate'].create({
                        'name': fecha_bcra,
                        'rate': float(valor),
                        'currency_id': ars_currency.id,
                    })

                else:
                    _logger.error("Error %s %s " % (data.status_code, data.reason))
                    data = False

        except Exception as e:
            _logger.error(e)
            raise Warning("Error %s" % repr(e))
