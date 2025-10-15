import datetime
import math

from celery import shared_task
from termcolor import colored

from main.configs import etl_config

URL = f"{etl_config.GDACS_URL}/gdacsapi/api/events/geteventlist/SEARCH"

countries = [
    "Afghanistan",
    "Albania",
    "Algeria",
    "American Samoa",
    "Andorra",
    "Angola",
    "Anguilla",
    "Antarctica",
    "Antigua & Barbuda",
    "Argentina",
    "Armenia",
    "Aruba",
    "Australia",
    "Austria",
    "Azerbaijan",
    "Bahrain",
    "Baker I.",
    "Bangladesh",
    "Barbados",
    "Belarus",
    "Belgium",
    "Belize",
    "Benin",
    "Bermuda",
    "Bhutan",
    "Bolivia",
    "Bosnia & Herzegovina",
    "Botswana",
    "Bouvet I.",
    "Brazil",
    "British Indian Ocean Territory",
    "British Virgin Is.",
    "Brunei",
    "Bulgaria",
    "Burkina Faso",
    "Burundi",
    "Cambodia",
    "Cameroon",
    "Canada",
    "Cape Verde",
    "Cayman Is.",
    "Central African Republic",
    "Chad",
    "Chile",
    "China",
    "Christmas I.",
    "Cocos Is.",
    "Colombia",
    "Comoros",
    "Cook Is.",
    "Costa Rica",
    "Cote d'Ivoire",
    "Croatia",
    "Cuba",
    "Cyprus",
    "Czech Republic",
    "Democratic Republic of Congo",
    "Denmark",
    "Djibouti",
    "Dominica",
    "Dominican Republic",
    "Ecuador",
    "Egypt",
    "El Salvador",
    "Equatorial Guinea",
    "Eritrea",
    "Estonia",
    "Eswatini",
    "Ethiopia",
    "Falkland Is.",
    "Faroe Is.",
    "Fiji",
    "Finland",
    "France",
    "French Guiana",
    "French Polynesia",
    "French Southern & Antarctic Lands",
    "Gabon",
    "Gaza Strip",
    "Georgia",
    "Germany",
    "Ghana",
    "Gibraltar",
    "Glorioso Is.",
    "Greece",
    "Greenland",
    "Grenada",
    "Guadeloupe",
    "Guam",
    "Guatemala",
    "Guernsey",
    "Guinea",
    "Guinea-Bissau",
    "Guyana",
    "Haiti",
    "Heard I. & McDonald Is.",
    "Honduras",
    "Howland I.",
    "Hungary",
    "Iceland",
    "India",
    "Indonesia",
    "Iraq",
    "Ireland",
    "Islamic Republic of Iran",
    "Isle of Man",
    "Israel",
    "Italy",
    "Jamaica",
    "Jan Mayen",
    "Japan",
    "Jarvis I.",
    "Jersey",
    "Johnston Atoll",
    "Jordan",
    "Juan De Nova I.",
    "Kazakhstan",
    "Kenya",
    "Kiribati",
    "Kosovo",
    "Kuwait",
    "Kyrgyzstan",
    "La Reunion",
    "Laos",
    "Latvia",
    "Lebanon",
    "Lesotho",
    "Liberia",
    "Libya",
    "Liechtenstein",
    "Lithuania",
    "Luxembourg",
    "Madagascar",
    "Malawi",
    "Malaysia",
    "Maldives",
    "Mali",
    "Malta",
    "Marshall Is.",
    "Martinique",
    "Mauritania",
    "Mauritius",
    "Mayotte",
    "Mexico",
    "Micronesia",
    "Midway Is.",
    "Moldova",
    "Monaco",
    "Mongolia",
    "Montenegro",
    "Montserrat",
    "Morocco",
    "Mozambique",
    "Myanmar",
    "Namibia",
    "Nauru",
    "Nepal",
    "Netherlands",
    "Netherlands Antilles",
    "New Caledonia",
    "New Zealand",
    "Nicaragua",
    "Niger",
    "Nigeria",
    "Niue",
    "Norfolk I.",
    "North Korea",
    "Northern Mariana Is.",
    "Norway",
    "Oman",
    "Pakistan",
    "Palau",
    "Panama",
    "Papua New Guinea",
    "Paraguay",
    "Peru",
    "Philippines",
    "Pitcairn Is.",
    "Poland",
    "Portugal",
    "Puerto Rico",
    "Qatar",
    "Republic of Congo",
    "Romania",
    "Russia",
    "Rwanda",
    "Samoa",
    "San Marino",
    "Sao Tome & Principe",
    "Saudi Arabia",
    "Senegal",
    "Serbia",
    "Seychelles",
    "Sierra Leone",
    "Singapore",
    "Slovakia",
    "Slovenia",
    "Solomon Is.",
    "Somalia",
    "South Africa",
    "South Georgia & the South Sandwich Is.",
    "South Korea",
    "South Sudan",
    "Spain",
    "Sri Lanka",
    "St. Helena",
    "St. Kitts & Nevis",
    "St. Lucia",
    "St. Pierre & Miquelon",
    "St. Vincent & the Grenadines",
    "Sudan",
    "Suriname",
    "Svalbard",
    "Sweden",
    "Switzerland",
    "Syria",
    "Taiwan",
    "Tajikistan",
    "Tanzania",
    "Thailand",
    "The Bahamas",
    "The Gambia",
    "The Republic of North Macedonia",
    "Timor-Leste",
    "Togo",
    "Tokelau",
    "Tonga",
    "Trinidad & Tobago",
    "Tunisia",
    "Türkiye",
    "Turkmenistan",
    "Turks & Caicos Is.",
    "Tuvalu",
    "Uganda",
    "Ukraine",
    "United Arab Emirates",
    "United Kingdom",
    "United States",
    "Uruguay",
    "Uzbekistan",
    "Vanuatu",
    "Vatican City",
    "Venezuela",
    "Vietnam",
    "Virgin Is.",
    "Wake I.",
    "Wallis & Futuna",
    "West Bank",
    "Western Sahara",
    "Yemen",
    "Zambia",
    "Zimbabwe",
    "",
]
alert_levels = ["Red", "Orange", "Green"]


def increment_date(my_date, NUM):
    return my_date + datetime.timedelta(days=NUM)


def get_gdacs_url(
    hazard,
    start_date,
    end_date,
    alert_level,
    country,
):
    url = f"{etl_config.GDACS_URL}/gdacsapi/api/events/geteventlist/SEARCH?eventlist={hazard}&fromDate={start_date}&toDate={end_date}"  # noqa
    if alert_level is None:
        url += "&alertlevel=Green;Orange;Red"
    else:
        url += f"&alertlevel={alert_level}"

    if country is not None:
        url += f"&country={country}"

    return url


@shared_task
def deep_dive(session, hazard, start_date, end_date, NUM, indent):
    parameter_dict_list = []
    iter_date = start_date
    iteration = 1

    total_items = 0

    while iter_date <= end_date:
        session_end_date = min(increment_date(iter_date, NUM - 1), end_date)

        response = session.get(get_gdacs_url(hazard, iter_date, session_end_date, None, None))
        if response.status_code == 200:
            data = response.json()
            items = len(data["features"])
            if items >= 100:
                if iter_date == session_end_date:
                    for alert_level in alert_levels:
                        response = session.get(get_gdacs_url(hazard, iter_date, session_end_date, alert_level, None))
                        if response.status_code == 200:
                            data = response.json()
                            items = len(data["features"])
                            if items >= 100:
                                for country in countries:
                                    response = session.get(
                                        get_gdacs_url(hazard, iter_date, session_end_date, alert_level, country)
                                    )
                                    if response.status_code == 200:
                                        data = response.json()
                                        items = len(data["features"])
                                        if items >= 100:
                                            print(
                                                colored(
                                                    f"{indent}Bad: {iter_date} to {session_end_date} for {hazard}, {alert_level}, {country} and got {items} items",  # noqa
                                                    "red",
                                                )
                                            )
                                            total_items += 100
                                        else:
                                            print(
                                                colored(
                                                    f"{indent}Good: {iter_date} to {session_end_date} for {hazard}, {alert_level}, {country} and got {items} items",  # noqa
                                                    "green",
                                                )
                                            )

                                            data = {
                                                "fromDate": str(iter_date),
                                                "toDate": str(session_end_date),
                                                "alertlevel": alert_level,
                                                "eventlist": hazard,
                                                "country": country,
                                            }
                                            parameter_dict_list.append(data)

                                            total_items += items
                                    elif response.status_code == 204:
                                        print(
                                            colored(
                                                f"{indent}Good: {iter_date} to {session_end_date} for {hazard}, {alert_level}, {country} and got 0 items",  # noqa
                                                "green",
                                            )
                                        )
                                        total_items += 0
                                    else:
                                        print(colored(f"{indent}Bad: {response.status_code}", "red"))
                                        total_items += 0
                            else:
                                print(
                                    colored(
                                        f"{indent}Good: {iter_date} to {session_end_date} for {hazard}, {alert_level} and got {items} items",  # noqa
                                        "green",
                                    )
                                )
                                data = {
                                    "fromDate": str(iter_date),
                                    "toDate": str(session_end_date),
                                    "alertlevel": alert_level,
                                    "eventlist": hazard,
                                    "country": None,
                                }
                                parameter_dict_list.append(data)
                                total_items += items
                        elif response.status_code == 204:
                            print(
                                colored(
                                    f"{indent}Good: {iter_date} to {session_end_date} for {hazard}, {alert_level} and got 0 items",  # noqa
                                    "green",
                                )
                            )
                            total_items += 0
                        else:
                            print(colored(f"{indent}Bad: {response.status_code}", "red"))
                            total_items += 0
                else:
                    NEW_NUM = math.ceil(NUM / 2)
                    print(
                        colored(
                            f"{indent}Splitting: {iter_date} to {session_end_date} for {hazard} and got {items} items",
                            "yellow",
                        )
                    )
                    total_items += deep_dive(session, hazard, iter_date, session_end_date, NEW_NUM, indent + "  ")
            else:
                print(
                    colored(f"{indent}Good: {iter_date} to {session_end_date} for {hazard} and got {items} items", "green")
                )
                data = {
                    "fromDate": str(iter_date),
                    "toDate": str(session_end_date),
                    "alertlevel": "Green;Orange;Red",
                    "eventlist": hazard,
                    "country": None,
                }
                parameter_dict_list.append(data)

                total_items = items
        elif response.status_code == 204:
            print(colored(f"{indent}Good: {iter_date} to {session_end_date} for {hazard} and got 0 items", "green"))
            total_items += 0
        else:
            print(colored(f"{indent}Bad: {response.status_code}", "red"))
            total_items += 0

        next_date = increment_date(iter_date, NUM)

        iter_date = next_date
        iteration += 1

    return parameter_dict_list
