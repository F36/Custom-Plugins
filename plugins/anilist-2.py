import os
from datetime import datetime

import flag as cflag
import humanize
from aiohttp import ClientSession
from userge import Message, get_collection, userge
from userge.utils import post_to_telegraph as post_to_tp

# Logging Errors
CLOG = userge.getCLogger(__name__)

# Default templates for Query Formatting
ANIME_TEMPLATE = """[{c_flag}]**{romaji}**
        __{english}__
        {native}

**ID | MAL ID:** `{idm}` | `{idmal}`
**SOURCE:** `{source}`
🆎 **TYPE:** `{formats}`
🎭 **GENRES:** `{genre}`
🎋 **SEASON:** `{season}`
🔢 **EPISODES:** `{episodes}`
🕓 **DURATION:** `{duration} min/ep`
➤ **CHARACTERS:** `{chrctrs}`
📡 **STATUS:** `{status}`
📺 **NEXT AIRING:** `{air_on}`
💯 **SCORE:** `{score}/100`
🔞 **ADULT RATED:** `{adult}`
🎬 {trailer_link}
📖 [Synopsis & More]({synopsis_link})"""

SAVED = get_collection("TEMPLATES")

# GraphQL Queries.
ANIME_QUERY = """
query ($id: Int, $idMal:Int, $search: String, $type: MediaType, $asHtml: Boolean) {
  Media (id: $id, idMal: $idMal, search: $search, type: $type) {
    id
    idMal
    title {
      romaji
      english
      native
    }
    format
    status
    description (asHtml: $asHtml)
    startDate {
      year
      month
      day
    }
    season
    episodes
    duration
    countryOfOrigin
    source (version: 2)
    trailer {
      id
      site
      thumbnail
    }
    coverImage {
      extraLarge
    }
    bannerImage
    genres
    averageScore
    nextAiringEpisode {
      airingAt
      timeUntilAiring
      episode
    }
    isAdult
    characters (role: MAIN, page: 1, perPage: 10) {
      nodes {
        id
        name {
          full
          native
        }
        image {
          large
        }
        description (asHtml: $asHtml)
        siteUrl
      }
    }
    studios (isMain: true) {
      nodes {
        name
        siteUrl
      }
    }
    siteUrl
  }
}
"""

AIRING_QUERY = """
query ($id: Int, $mediaId: Int, $notYetAired: Boolean) {
  Page(page: 1, perPage: 50) {
    airingSchedules (id: $id, mediaId: $mediaId, notYetAired: $notYetAired) {
      id
      airingAt
      timeUntilAiring
      episode
      mediaId
      media {
        title {
          romaji
          english
          native
        }
        duration
        coverImage {
          extraLarge
        }
        nextAiringEpisode {
          airingAt
          timeUntilAiring
          episode
        }
        bannerImage
        averageScore
        siteUrl
      }
    }
  }
}
"""

CHARACTER_QUERY = """
query ($search: String, $asHtml: Boolean) {
  Character (search: $search) {
    id
    name {
      full
      native
    }
    image {
      large
    }
    description (asHtml: $asHtml)
    siteUrl
    media (page: 1, perPage: 25) {
      nodes {
        id
        idMal
        title {
          romaji
          english
          native
        }
        type
        siteUrl
        coverImage {
          extraLarge
        }
        bannerImage
        averageScore
        description (asHtml: $asHtml)
      }
    }
  }
}
"""


async def _init():
    global ANIME_TEMPLATE  # pylint: disable=global-statement
    template = await SAVED.find_one({"_id": "ANIME_TEPLATE"})
    if template:
        ANIME_TEMPLATE = template["anime_data"]


async def return_json_senpai(query, vars_):
    """ Makes a Post to https://graphql.anilist.co. """
    url_ = "https://graphql.anilist.co"
    async with ClientSession() as session:
        async with session.post(
            url_, json={"query": query, "variables": vars_}
        ) as post_con:
            json_data = await post_con.json()
    return json_data


def make_it_rw(time_stamp, as_countdown=False):
    """ Converting Time Stamp to Readable Format """
    if as_countdown:
        now = datetime.now()
        air_time = datetime.fromtimestamp(time_stamp)
        return str(humanize.naturaltime(now - air_time))
    return str(humanize.naturaldate(datetime.fromtimestamp(time_stamp)))


@userge.on_cmd(
    "ani",
    about={
        "header": "Anime Search",
        "description": "Search for Anime using AniList API",
        "flags": {"-mid": "Search Anime using MAL ID", "-wp": "Get webpage previews "},
        "usage": "{tr}anime [flag] [anime name | ID]",
        "examples": [
            "{tr}anime 98444",
            "{tr}anime -mid 39576",
            "{tr}anime Asterisk war",
        ],
    },
)
async def anim_arch(message: Message):
    """ Search Anime Info """
    query = message.filtered_input_str
    if not query:
        await message.err("NameError: 'query' not defined")
        return
    vars_ = {"search": query, "asHtml": True, "type": "ANIME"}
    if query.isdigit():
        vars_ = {"id": int(query), "asHtml": True, "type": "ANIME"}
        if "-mid" in message.flags:
            vars_ = {"idMal": int(query), "asHtml": True, "type": "ANIME"}

    result = await return_json_senpai(ANIME_QUERY, vars_)
    error = result.get("errors")
    if error:
        await CLOG.log(f"**ANILIST RETURNED FOLLOWING ERROR:**\n\n`{error}`")
        error_sts = error[0].get("message")
        await message.err(f"[{error_sts}]")
        return

    data = result["data"]["Media"]

    # Data of all fields in returned json
    # pylint: disable=possibly-unused-variable
    idm = data.get("id")
    idmal = data.get("idMal")
    romaji = data["title"]["romaji"]
    english = (
        data["title"]["english"] if data["title"]["english"] != None else "--------"
    )
    native = data["title"]["native"]
    formats = data.get("format")
    status = data.get("status")
    synopsis = data.get("description")
    season = data.get("season")
    episodes = data.get("episodes")
    duration = data.get("duration")
    country = data.get("countryOfOrigin")
    c_flag = cflag.flag(country)
    source = data.get("source")
    coverImg = data.get("coverImage")["extraLarge"]
    bannerImg = data.get("bannerImage")
    genres = data.get("genres")
    charlist = []
    for char in data["characters"]["nodes"]:
        charlist.append(f"    •{char['name']['full']}")
    chrctrs = "\n"
    chrctrs += ("\n").join(charlist[:10])
    genre = genres[0]
    if len(genres) != 1:
        genre = ", ".join(genres)
    score = data.get("averageScore")
    air_on = None
    if data["nextAiringEpisode"]:
        nextAir = data["nextAiringEpisode"]["airingAt"]
        air_on = make_it_rw(nextAir)
        air_on += f" | {data['nextAiringEpisode']['episode']}th eps"
    s_date = data.get("startDate")
    adult = data.get("isAdult")
    trailer_link = "N/A"

    if data["trailer"] and data["trailer"]["site"] == "youtube":
        trailer_link = f"[Trailer](https://youtu.be/{data['trailer']['id']})"
    html_char = ""
    for character in data["characters"]["nodes"]:
        html_ = ""
        html_ += "<br>"
        html_ += f"""<a href="{character['siteUrl']}">"""
        html_ += f"""<img src="{character['image']['large']}"/></a>"""
        html_ += "<br>"
        html_ += f"<h3>{character['name']['full']}</h3>"
        html_ += f"<em>{c_flag} {character['name']['native']}</em><br>"
        html_ += f"<b>Character ID</b>: {character['id']}<br>"
        html_ += (
            f"<h4>About Character and Role:</h4>{character.get('description', 'N/A')}"
        )
        html_char += f"{html_}<br><br>"

    studios = "".join(
        "<a href='{}'>• {}</a> ".format(studio["siteUrl"], studio["name"])
        for studio in data["studios"]["nodes"]
    )

    url = data.get("siteUrl")

    title_img = coverImg or bannerImg
    # Telegraph Post mejik
    html_pc = ""
    html_pc += f"<img src='{title_img}' title={romaji}/>"
    html_pc += f"<h1>[{c_flag}] {native}</h1>"
    html_pc += "<h3>Synopsis:</h3>"
    html_pc += synopsis
    html_pc += "<br>"
    if html_char:
        html_pc += "<h2>Main Characters:</h2>"
        html_pc += html_char
        html_pc += "<br><br>"
    html_pc += "<h3>More Info:</h3>"
    html_pc += f"<b>Started On:</b> {s_date['day']}/{s_date['month']}/{s_date['year']}"
    html_pc += f"<br><b>Studios:</b> {studios}<br>"
    html_pc += f"<a href='https://myanimelist.net/anime/{idmal}'>View on MAL</a>"
    html_pc += f"<a href='{url}'> View on anilist.co</a>"
    html_pc += f"<img src='{bannerImg}'/>"

    title_h = english or romaji
    synopsis_link = post_to_tp(title_h, html_pc)
    try:
        finals_ = ANIME_TEMPLATE.format(**locals())
    except KeyError as kys:
        await message.err(kys)
        return

    if "-wp" in message.flags:
        finals_ = f"[\u200b]({title_img}) {finals_}"
        await message.edit(finals_)
        return
    if len(finals_) <= 1023:
        await message.reply_photo(title_img, caption=finals_)
    else:
        await message.reply(finals_)
    await message.delete()


@userge.on_cmd(
    "char",
    about={
        "header": "Anime Character",
        "description": "Get Info about a Character and much more",
        "usage": "{tr}character [Name of Character]",
        "examples": "{tr}character Subaru Natsuki",
    },
)
async def character_search(message: Message):
    """ Get Info about a Character """
    query = message.input_str
    if not query:
        await message.err("NameError: 'query' not defined")
        return
    var = {"search": query, "asHtml": True}
    result = await return_json_senpai(CHARACTER_QUERY, var)
    error = result.get("errors")
    if error:
        await CLOG.log(f"**ANILIST RETURNED FOLLOWING ERROR:**\n\n`{error}`")
        error_sts = error[0].get("message")
        await message.err(f"[{error_sts}]")
        return

    data = result["data"]["Character"]

    # Character Data
    id_ = data["id"]
    name = data["name"]["full"]
    native = data["name"]["native"]
    img = data["image"]["large"]
    site_url = data["siteUrl"]
    description = data["description"]
    featured = data["media"]["nodes"]
    snin = "\n"
    for ani in featured:
        k = ani["title"]["english"] or ani["title"]["romaji"]
        kk = ani["type"]
        snin += f"    • {k} <code>[{kk}]</code> \n"
    sp = 0
    cntnt = ""
    for cf in featured:
        out = "<br>"
        out += f"""<img src="{cf['coverImage']['extraLarge']}"/>"""
        out += "<br>"
        title = cf["title"]["english"] or cf["title"]["romaji"]
        out += f"<h3>{title}</h3>"
        out += f"<em>[🇯🇵] {cf['title']['native']}</em><br>"
        out += f"""<a href="{cf['siteUrl']}>{cf['type']}</a><br>"""
        out += f"<b>Media ID:</b> {cf['id']}<br>"
        out += f"<b>SCORE:</b> {cf['averageScore']}/100<br>"
        out += cf.get("description", "N/A") + "<br>"
        cntnt += out
        sp += 1
        out = ""
        if sp > 5:
            break

    html_cntnt = f"<img src='{img}' title={name}/>"
    html_cntnt += f"<h1>[🇯🇵] {native}</h1>"
    html_cntnt += "<h3>About Character:</h3>"
    html_cntnt += description
    html_cntnt += "<br>"
    if cntnt:
        html_cntnt += "<h2>Top Featured Anime</h2>"
        html_cntnt += cntnt
        html_cntnt += "<br><br>"
    url_ = post_to_tp(name, html_cntnt)
    cap_text = f"""[🇯🇵] __{native}__
    (`{name}`)
**ID:** {id_}

**Featured in:** __{snin}__

[About Character]({url_})
[Visit Website]({site_url})"""

    if len(cap_text) <= 1023:
        await message.reply_photo(img, caption=cap_text)
    else:
        await message.reply(cap_text)
    await message.delete()
