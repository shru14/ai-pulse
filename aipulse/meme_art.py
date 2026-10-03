"""The memes' cartoons, drawn here as SVG and saved once as PNG pictures in templates/memes/ (email can't show SVG).

Every picture is our own drawing of a generic cast: a techie in a hoodie, two women and a robot. No meme photo, film
still or real person's likeness is used; the scenes only follow the well-known layouts of meme formats (a layout is
an idea, the photos are someone's work). The pictures carry no news: the day's words go beside them in the email.

Redraw the pictures (needs Microsoft Edge, run on your own computer; the PNGs are committed):
    python -m aipulse.meme_art
"""

from __future__ import annotations

import math
import subprocess
import tempfile
from pathlib import Path

INK = "#1d2433"
SW = 3  # outline width
SKIN = {"light": "#F2C9A0", "mid": "#C68A5E", "deep": "#8D5A3B"}
HAIR = {"black": "#22201f", "dark": "#2b1d16", "auburn": "#9c4a22"}
DEV = {"skin": SKIN["mid"], "hair": "short", "hair_colour": HAIR["black"], "shirt": "#4F6BED", "glasses": True}
BOSSY = {"skin": SKIN["deep"], "hair": "curly", "hair_colour": HAIR["dark"], "shirt": "#E8833A", "glasses": False}
PARTNER = {"skin": SKIN["light"], "hair": "pony", "hair_colour": HAIR["auburn"], "shirt": "#2FA37C", "glasses": False}


def _o(fill: str, width: float = SW) -> str:
    return f'fill="{fill}" stroke="{INK}" stroke-width="{width}" stroke-linejoin="round" stroke-linecap="round"'


def hair_back(p: dict, cx: float, cy: float, r: float) -> str:
    c = p["hair_colour"]
    if p["hair"] == "curly":
        return f'<circle cx="{cx}" cy="{cy - r * .25}" r="{r * 1.38}" {_o(c)}/>'
    if p["hair"] == "pony":
        return (f'<path d="M{cx + r * .6},{cy - r * .7} q{r * 1.1},{r * .1} {r * .95},{r * 1.5} q-{r * .15},{r * .5} -{r * .5},{r * .7} '
                f'q{r * .2},-{r * .9} -{r * .55},-{r * 1.6}z" {_o(c)}/>')
    return ""


def hair_front(p: dict, cx: float, cy: float, r: float) -> str:
    c = p["hair_colour"]
    if p["hair"] == "curly":
        bumps = "".join(f'<circle cx="{cx + r * .92 * math.cos(math.radians(a))}" cy="{cy - r * .2 + r * .92 * math.sin(math.radians(a))}" '
                        f'r="{r * .3}" fill="{c}"/>' for a in range(200, 345, 24))
        return bumps
    return (f'<path d="M{cx - r * 1.02},{cy - r * .05} Q{cx - r * 1.05},{cy - r * 1.18} {cx},{cy - r * 1.12} '
            f'Q{cx + r * 1.05},{cy - r * 1.18} {cx + r * 1.02},{cy - r * .05} Q{cx + r * .75},{cy - r * .62} {cx + r * .1},{cy - r * .58} '
            f'Q{cx - r * .55},{cy - r * .62} {cx - r * 1.02},{cy - r * .05}Z" {_o(c)}/>')


def eyes(cx, cy, r, kind="dot", look=0.0, glasses=False):
    out, lx, rx, ey = [], cx - r * .36, cx + r * .36, cy + r * .02
    for x in (lx, rx):
        if kind == "dot":
            out.append(f'<circle cx="{x + look * r * .08}" cy="{ey}" r="{r * .08}" fill="{INK}"/>')
        elif kind == "big":
            out.append(f'<circle cx="{x}" cy="{ey}" r="{r * .2}" fill="#fff" stroke="{INK}" stroke-width="2.5"/>'
                       f'<circle cx="{x + look * r * .08}" cy="{ey}" r="{r * .07}" fill="{INK}"/>')
        elif kind == "closed":  # peaceful: a little smile of a line
            out.append(f'<path d="M{x - r * .14},{ey} q{r * .14},{r * .12} {r * .28},0" fill="none" stroke="{INK}" stroke-width="3" stroke-linecap="round"/>')
        elif kind == "shut":  # turned away: lines
            out.append(f'<path d="M{x - r * .14},{ey} h{r * .28}" stroke="{INK}" stroke-width="3" stroke-linecap="round"/>')
        elif kind == "happy":
            out.append(f'<path d="M{x - r * .14},{ey + r * .03} q{r * .14},-{r * .16} {r * .28},0" fill="none" stroke="{INK}" stroke-width="3" stroke-linecap="round"/>')
        elif kind == "half":  # smug, lids half down
            out.append(f'<circle cx="{x + look * r * .08}" cy="{ey + r * .02}" r="{r * .08}" fill="{INK}"/>'
                       f'<path d="M{x - r * .16},{ey - r * .04} h{r * .32}" stroke="{INK}" stroke-width="3" stroke-linecap="round"/>')
    if glasses:
        g = r * .23
        out.append(f'<circle cx="{lx}" cy="{ey}" r="{g}" fill="none" stroke="{INK}" stroke-width="2.6"/>'
                   f'<circle cx="{rx}" cy="{ey}" r="{g}" fill="none" stroke="{INK}" stroke-width="2.6"/>'
                   f'<path d="M{lx + g},{ey} h{rx - lx - 2 * g}" stroke="{INK}" stroke-width="2.6"/>')
    return "".join(out)


def brows(cx, cy, r, kind="flat"):
    lx, rx, by = cx - r * .36, cx + r * .36, cy - r * .3
    if kind == "angry":
        return (f'<path d="M{lx - r * .17},{by - r * .1} L{lx + r * .17},{by + r * .06}" stroke="{INK}" stroke-width="4" stroke-linecap="round"/>'
                f'<path d="M{rx + r * .17},{by - r * .1} L{rx - r * .17},{by + r * .06}" stroke="{INK}" stroke-width="4" stroke-linecap="round"/>')
    if kind == "worried":
        return (f'<path d="M{lx - r * .17},{by + r * .02} L{lx + r * .15},{by - r * .1}" stroke="{INK}" stroke-width="4" stroke-linecap="round"/>'
                f'<path d="M{rx + r * .17},{by + r * .02} L{rx - r * .15},{by - r * .1}" stroke="{INK}" stroke-width="4" stroke-linecap="round"/>')
    if kind == "up":
        return (f'<path d="M{lx - r * .15},{by - r * .08} q{r * .15},-{r * .1} {r * .3},0" fill="none" stroke="{INK}" stroke-width="4" stroke-linecap="round"/>'
                f'<path d="M{rx - r * .15},{by - r * .08} q{r * .15},-{r * .1} {r * .3},0" fill="none" stroke="{INK}" stroke-width="4" stroke-linecap="round"/>')
    if kind == "one":  # one raised: suspicious
        return (f'<path d="M{lx - r * .15},{by - r * .14} q{r * .15},-{r * .12} {r * .3},0" fill="none" stroke="{INK}" stroke-width="4" stroke-linecap="round"/>'
                f'<path d="M{rx - r * .15},{by + r * .02} h{r * .3}" stroke="{INK}" stroke-width="4" stroke-linecap="round"/>')
    return ""


def mouth(cx, cy, r, kind="smile"):
    my = cy + r * .45
    if kind == "smile":
        return f'<path d="M{cx - r * .28},{my - r * .06} q{r * .28},{r * .3} {r * .56},0" fill="none" stroke="{INK}" stroke-width="3.2" stroke-linecap="round"/>'
    if kind == "grin":
        return f'<path d="M{cx - r * .32},{my - r * .1} q{r * .32},{r * .42} {r * .64},0z" fill="#fff" stroke="{INK}" stroke-width="3" stroke-linejoin="round"/>'
    if kind == "frown":
        return f'<path d="M{cx - r * .24},{my + r * .1} q{r * .24},-{r * .2} {r * .48},0" fill="none" stroke="{INK}" stroke-width="3.2" stroke-linecap="round"/>'
    if kind == "o":
        return f'<ellipse cx="{cx}" cy="{my}" rx="{r * .12}" ry="{r * .15}" fill="{INK}"/>'
    if kind == "O":
        return f'<ellipse cx="{cx}" cy="{my + r * .02}" rx="{r * .2}" ry="{r * .26}" fill="#5a1f24" stroke="{INK}" stroke-width="3"/>'
    if kind == "yell":
        return (f'<path d="M{cx - r * .3},{my - r * .12} q{r * .3},-{r * .08} {r * .6},0 q-{r * .05},{r * .5} -{r * .3},{r * .5} '
                f'q-{r * .25},0 -{r * .3},-{r * .5}z" fill="#5a1f24" stroke="{INK}" stroke-width="3" stroke-linejoin="round"/>')
    if kind == "wobbly":
        return (f'<path d="M{cx - r * .3},{my} q{r * .1},-{r * .1} {r * .2},0 t{r * .2},0 t{r * .2},0" fill="none" stroke="{INK}" '
                f'stroke-width="3" stroke-linecap="round"/>')
    if kind == "smirk":
        return f'<path d="M{cx - r * .2},{my} q{r * .25},{r * .08} {r * .4},-{r * .14}" fill="none" stroke="{INK}" stroke-width="3.2" stroke-linecap="round"/>'
    if kind == "flat":
        return f'<path d="M{cx - r * .2},{my} h{r * .4}" stroke="{INK}" stroke-width="3.2" stroke-linecap="round"/>'
    return ""


def head(p: dict, cx, cy, r, eye="dot", brow="flat", mouth_kind="smile", look=0.0, blush=False, sweat=False):
    parts = [hair_back(p, cx, cy, r),
             f'<circle cx="{cx - r * .98}" cy="{cy + r * .1}" r="{r * .17}" {_o(p["skin"])}/>',
             f'<circle cx="{cx + r * .98}" cy="{cy + r * .1}" r="{r * .17}" {_o(p["skin"])}/>',
             f'<circle cx="{cx}" cy="{cy}" r="{r}" {_o(p["skin"])}/>',
             hair_front(p, cx, cy, r), eyes(cx, cy, r, eye, look, p.get("glasses")), brows(cx, cy, r, brow), mouth(cx, cy, r, mouth_kind)]
    if blush:
        parts.append(f'<ellipse cx="{cx - r * .55}" cy="{cy + r * .3}" rx="{r * .14}" ry="{r * .08}" fill="#e8838a" opacity=".6"/>'
                     f'<ellipse cx="{cx + r * .55}" cy="{cy + r * .3}" rx="{r * .14}" ry="{r * .08}" fill="#e8838a" opacity=".6"/>')
    if sweat:
        parts.append(drop(cx + r * .95, cy - r * .55, r * .2) + drop(cx - r * 1.05, cy - r * .2, r * .15))
    return "".join(parts)


def drop(x, y, s):
    return f'<path d="M{x},{y - s} q{s * .9},{s * 1.2} 0,{s * 1.8} q-{s * .9},-{s * .6} 0,-{s * 1.8}z" fill="#8fd3ff" stroke="{INK}" stroke-width="2"/>'


def torso(p: dict, cx, top, w, h):
    return (f'<path d="M{cx - w / 2},{top + h} L{cx - w / 2},{top + h * .3} Q{cx - w / 2},{top} {cx - w * .2},{top} '
            f'L{cx + w * .2},{top} Q{cx + w / 2},{top} {cx + w / 2},{top + h * .3} L{cx + w / 2},{top + h}z" {_o(p["shirt"])}/>'
            f'<path d="M{cx - w * .12},{top + 2} q{w * .12},{h * .16} {w * .24},0" fill="none" stroke="{INK}" stroke-width="2.4"/>')


def arm(p: dict, pts, hand="fist", width=17):
    d = "M" + " L".join(f"{x},{y}" for x, y in pts)
    hx, hy = pts[-1]
    px, py = pts[-2]
    ang = math.degrees(math.atan2(hy - py, hx - px))
    out = (f'<path d="{d}" fill="none" stroke="{INK}" stroke-width="{width + 6}" stroke-linecap="round" stroke-linejoin="round"/>'
           f'<path d="{d}" fill="none" stroke="{p["shirt"]}" stroke-width="{width}" stroke-linecap="round" stroke-linejoin="round"/>')
    if hand == "point":
        out += (f'<g transform="translate({hx},{hy}) rotate({ang})"><rect x="6" y="-4" width="22" height="9" rx="4.5" {_o(p["skin"], 2.5)}/>'
                f'<circle cx="0" cy="0" r="11" {_o(p["skin"])}/></g>')
    elif hand == "palm":  # an open hand, fingers up: "nope"
        out += (f'<g transform="translate({hx},{hy})"><rect x="-13" y="-22" width="26" height="30" rx="10" {_o(p["skin"])}/>'
                f'<path d="M-6,-20 v-6 M0,-21 v-8 M6,-20 v-6" stroke="{INK}" stroke-width="2.4" stroke-linecap="round"/></g>')
    elif hand == "open":  # palm out, sideways: the "is this...?" gesture
        out += (f'<g transform="translate({hx},{hy}) rotate({ang})"><ellipse cx="8" cy="0" rx="16" ry="11" {_o(p["skin"])}/>'
                f'<path d="M14,-8 l10,-6 M18,-2 l12,-2 M18,4 l11,3" stroke="{INK}" stroke-width="2.4" stroke-linecap="round"/></g>')
    else:
        out += f'<circle cx="{hx}" cy="{hy}" r="11" {_o(p["skin"])}/>'
    return out


def robot(cx, cy, s=1.0, eyes_kind="happy", sparkle=False, mouth_kind="smile"):
    """A friendly robot: cy is the middle of its head."""
    w, h = 96 * s, 74 * s
    out = [f'<path d="M{cx},{cy - h / 2} v-{18 * s}" stroke="{INK}" stroke-width="{SW}"/>',
           f'<circle cx="{cx}" cy="{cy - h / 2 - 22 * s}" r="{7 * s}" {_o("#E5484D")}/>',
           f'<rect x="{cx - w * .45}" y="{cy + h / 2}" width="{w * .9}" height="{70 * s}" rx="{14 * s}" {_o("#D9DEE8")}/>',
           f'<circle cx="{cx}" cy="{cy + h / 2 + 34 * s}" r="{9 * s}" {_o("#FFD25E")}/>',
           f'<rect x="{cx - w / 2 - 8 * s}" y="{cy - 10 * s}" width="{10 * s}" height="{22 * s}" rx="4" {_o("#AEB6C6")}/>',
           f'<rect x="{cx + w / 2 - 2 * s}" y="{cy - 10 * s}" width="{10 * s}" height="{22 * s}" rx="4" {_o("#AEB6C6")}/>',
           f'<rect x="{cx - w / 2}" y="{cy - h / 2}" width="{w}" height="{h}" rx="{18 * s}" {_o("#D9DEE8")}/>',
           f'<rect x="{cx - w * .38}" y="{cy - h * .32}" width="{w * .76}" height="{h * .64}" rx="{10 * s}" fill="{INK}"/>']
    ex, ey, e = 16 * s, cy - 4 * s, 7 * s
    glow = "#5CE1E6"
    if eyes_kind == "happy":
        for x in (cx - ex, cx + ex):
            out.append(f'<path d="M{x - e},{ey + 2 * s} q{e},-{e * 1.6} {e * 2},0" fill="none" stroke="{glow}" stroke-width="{3.5 * s}" stroke-linecap="round"/>')
    elif eyes_kind == "huh":
        out.append(f'<circle cx="{cx - ex}" cy="{ey}" r="{e * .7}" fill="{glow}"/><circle cx="{cx + ex}" cy="{ey - 1}" r="{e * 1.15}" fill="none" stroke="{glow}" stroke-width="{3 * s}"/>')
    elif eyes_kind == "heart":
        for x in (cx - ex, cx + ex):
            out.append(f'<path d="M{x},{ey + e} l-{e},-{e} a{e / 2},{e / 2} 0 0 1 {e},-{e * .6} a{e / 2},{e / 2} 0 0 1 {e},{e * .6}z" fill="#ff7aa2"/>')
    if mouth_kind == "smile":
        out.append(f'<path d="M{cx - 9 * s},{cy + 12 * s} q{9 * s},{8 * s} {18 * s},0" fill="none" stroke="{glow}" stroke-width="{3 * s}" stroke-linecap="round"/>')
    elif mouth_kind == "flat":
        out.append(f'<path d="M{cx - 8 * s},{cy + 14 * s} h{16 * s}" stroke="{glow}" stroke-width="{3 * s}" stroke-linecap="round"/>')
    if sparkle:
        for x, y, z in ((cx - w * .9, cy - h * .5, 12), (cx + w * .85, cy - h * .2, 15), (cx + w * .7, cy + h * .9, 10), (cx - w * .8, cy + h * .8, 9)):
            out.append(star(x, y, z * s))
    return "".join(out)


def star(x, y, s, fill="#FFD25E"):
    return (f'<path d="M{x},{y - s} Q{x + s * .18},{y - s * .18} {x + s},{y} Q{x + s * .18},{y + s * .18} {x},{y + s} '
            f'Q{x - s * .18},{y + s * .18} {x - s},{y} Q{x - s * .18},{y - s * .18} {x},{y - s}z" fill="{fill}" stroke="{INK}" stroke-width="2"/>')


def svg(w, h, body, bg):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">'
            f'<rect width="{w}" height="{h}" fill="{bg}"/>{body}</svg>')


def flame(x, base, h, w):
    return (f'<path d="M{x - w / 2},{base} Q{x - w * .7},{base - h * .5} {x - w * .1},{base - h * .65} Q{x - w * .25},{base - h * .9} {x},{base - h} '
            f'Q{x + w * .15},{base - h * .7} {x + w * .35},{base - h * .75} Q{x + w * .75},{base - h * .4} {x + w / 2},{base}z" fill="#F26B3A" stroke="{INK}" stroke-width="2.5"/>'
            f'<path d="M{x - w * .25},{base} Q{x - w * .3},{base - h * .35} {x},{base - h * .55} Q{x + w * .3},{base - h * .3} {x + w * .25},{base}z" fill="#FFD25E"/>')


# ---------- The scenes ----------

def nope():
    """Two-panel "nope / yep" (the Drake layout), panel one: hand up, face turned away."""
    p, b = DEV, []
    b.append(torso(p, 130, 165, 150, 120))
    b.append(head(p, 122, 105, 58, eye="shut", brow="angry", mouth_kind="frown"))
    b.append(arm(p, [(185, 190), (215, 160), (205, 112)], "palm"))
    return svg(300, 260, "".join(b), "#F6C453")


def yep():
    p, b = DEV, []
    b.append(torso(p, 120, 165, 150, 120))
    b.append(arm(p, [(175, 195), (225, 170), (262, 150)], "point"))
    b.append(head(p, 128, 102, 58, eye="happy", brow="up", mouth_kind="grin", blush=True))
    return svg(300, 260, "".join(b), "#F6C453")


def distracted():
    """The "distracted" layout: someone turns to stare at the shiny new thing while their partner glares."""
    b = ['<rect y="0" width="600" height="230" fill="#CFE8FF"/>',
         '<rect x="20" y="60" width="90" height="170" fill="#E9EEF5" stroke="#b9c3d3" stroke-width="2"/>',
         '<rect x="470" y="40" width="110" height="190" fill="#E9EEF5" stroke="#b9c3d3" stroke-width="2"/>',
         *(f'<rect x="{x}" y="{y}" width="18" height="22" fill="#b9d6f2"/>' for x in (36, 70, 488, 524, 556) for y in (80, 120, 160)),
         '<rect y="230" width="600" height="110" fill="#E7E2D8"/>', '<path d="M0,232 H600" stroke="#c9c1b0" stroke-width="3"/>']
    b.append(robot(120, 140, 1.05, eyes_kind="happy", sparkle=True))
    b.append(torso(DEV, 300, 210, 140, 130))
    b.append(arm(DEV, [(245, 235), (225, 280), (255, 315)]))
    b.append(head(DEV, 290, 152, 56, eye="big", brow="up", mouth_kind="o", look=-1.5))
    b.append(torso(PARTNER, 480, 220, 130, 120))
    b.append(arm(PARTNER, [(430, 245), (408, 285), (440, 300)]))
    b.append(arm(PARTNER, [(530, 245), (552, 285), (520, 300)]))
    b.append(head(PARTNER, 480, 165, 52, eye="dot", brow="angry", mouth_kind="frown", look=-1.5))
    return svg(600, 340, "".join(b), "#CFE8FF")


def fine():
    """The "this is fine" layout: calm at a desk while the room burns."""
    b = ['<rect width="600" height="320" fill="#F3B04A"/>',
         '<ellipse cx="160" cy="30" rx="170" ry="45" fill="#8a8f99" opacity=".75"/>',
         '<ellipse cx="420" cy="20" rx="210" ry="40" fill="#8a8f99" opacity=".7"/>',
         # a server rack, smoking
         f'<rect x="40" y="90" width="110" height="200" rx="6" {_o("#3a4252")}/>',
         *(f'<rect x="52" y="{y}" width="86" height="22" rx="3" fill="#596377"/><circle cx="128" cy="{y + 11}" r="3.5" fill="{c}"/>'
           for y, c in ((104, "#E5484D"), (134, "#E5484D"), (164, "#FFD25E"), (194, "#E5484D"), (224, "#E5484D"), (254, "#E5484D"))),
         flame(95, 92, 70, 70), flame(30, 320, 120, 70), flame(175, 320, 80, 60), flame(575, 320, 130, 70), flame(520, 320, 70, 50)]
    # the desk, the laptop, the coffee
    b.append(torso(DEV, 365, 200, 140, 120))
    b.append(head(DEV, 365, 140, 56, eye="big", brow="flat", mouth_kind="smile", look=0))
    b.append(f'<rect x="250" y="262" width="260" height="16" rx="3" {_o("#8B5E3C")}/>')
    b.append(f'<path d="M300,262 l20,-46 h86 l-12,46z" {_o("#C9CED8")}/>')
    b.append(arm(DEV, [(420, 225), (450, 250), (450, 236)]))
    b.append(f'<rect x="440" y="226" width="26" height="34" rx="4" {_o("#ffffff")}/><path d="M466,234 q12,0 12,10 q0,10 -12,10" fill="none" stroke="{INK}" stroke-width="3"/>')
    b.append('<path d="M448,220 q-6,-10 0,-18 M458,220 q-6,-10 0,-18" fill="none" stroke="#fff" stroke-width="2.5" opacity=".8"/>')
    # the speech bubble
    b.append(f'<rect x="420" y="58" width="160" height="58" rx="18" {_o("#ffffff")}/><path d="M440,114 l-26,22 l44,-22" {_o("#ffffff")}/>'
             f'<path d="M442,113 h18" stroke="#fff" stroke-width="5"/>'
             f'<text x="500" y="96" text-anchor="middle" font-family="Arial,Helvetica,sans-serif" font-weight="900" font-size="22" fill="{INK}">This is fine.</text>')
    return svg(600, 320, "".join(b), "#F3B04A")


def buttons():
    """The "two buttons" layout: two big red buttons, then the sweat."""
    b = [f'<rect x="60" y="20" width="480" height="150" rx="16" {_o("#C9CED8")}/>',
         f'<rect x="60" y="20" width="480" height="18" rx="9" fill="#AEB6C6"/>']
    for x in (180, 420):
        b.append(f'<ellipse cx="{x}" cy="112" rx="70" ry="22" fill="#8a1c22" stroke="{INK}" stroke-width="{SW}"/>'
                 f'<path d="M{x - 70},112 v-18 a70,22 0 0 1 140,0 v18" fill="#E5484D" stroke="{INK}" stroke-width="{SW}"/>'
                 f'<ellipse cx="{x}" cy="94" rx="70" ry="22" fill="#F06A6F" stroke="{INK}" stroke-width="{SW}"/>'
                 f'<ellipse cx="{x - 22}" cy="88" rx="20" ry="6" fill="#fff" opacity=".5"/>')
    b.append(torso(DEV, 300, 335, 170, 110))
    b.append(arm(DEV, [(225, 365), (205, 330), (238, 268)]))
    b.append(head(DEV, 300, 280, 62, eye="big", brow="worried", mouth_kind="wobbly", sweat=True))
    b.append(f'<path d="M226,262 q16,-14 40,-2 l-6,16 q-18,-8 -30,2z" fill="#fff" stroke="{INK}" stroke-width="2.5"/>')  # the hanky
    b.append(drop(380, 230, 9) + drop(205, 300, 8))
    return svg(600, 445, "".join(b), "#F4F1EA")


def brain(level: int):
    """The "expanding brain" layout: a head in profile, its brain bigger and brighter each row."""
    bg = ["#FFFFFF", "#F4E9FF", "#E2D4FF", "#141925"][level - 1]
    b = []
    if level == 4:
        b += [star(x, y, s, "#FFF4B8") for x, y, s in ((30, 30, 6), (175, 25, 8), (160, 105, 5), (20, 110, 5), (110, 14, 4))]
        b.append('<circle cx="95" cy="70" r="70" fill="#7b5cff" opacity=".35"/><circle cx="95" cy="70" r="52" fill="#a993ff" opacity=".35"/>')
    if level == 3:
        b += [f'<path d="M95,70 L{95 + 80 * math.cos(math.radians(a))},{70 + 80 * math.sin(math.radians(a))}" stroke="#FFD25E" stroke-width="5"/>'
              for a in range(0, 360, 30)]
    # head in profile, facing right
    skin = "#ffe9c7" if level == 4 else "#E9EDF4"
    b.append(f'<path d="M58,128 Q50,96 56,74 Q52,22 102,18 Q150,16 152,62 Q156,70 164,82 Q166,88 156,90 Q158,104 150,112 '
             f'Q142,116 132,114 L132,128z" fill="{skin}" stroke="{INK}" stroke-width="{SW}" opacity="{1 if level < 4 else .95}"/>')
    size = [14, 22, 30, 36][level - 1]
    col = ["#b8bcc6", "#f4a6c0", "#ff7aa2", "#fff4b8"][level - 1]
    b.append(f'<ellipse cx="100" cy="{52}" rx="{size * 1.3}" ry="{size}" fill="{col}" stroke="{INK}" stroke-width="2.5"/>'
             f'<path d="M{100 - size * .8},{52 - size * .2} q{size * .4},-{size * .5} {size * .8},0 t{size * .8},0 M{100 - size * .6},{52 + size * .35} '
             f'q{size * .4},-{size * .4} {size * .8},0" fill="none" stroke="{INK}" stroke-width="2" opacity=".6"/>')
    if level == 4:
        b.append(f'<ellipse cx="100" cy="52" rx="60" ry="46" fill="none" stroke="#fff4b8" stroke-width="3" opacity=".8"/>')
    return svg(190, 140, "".join(b), bg)


def yelling():
    """The "yelling at the cat" layout, with a robot at the dinner table."""
    b = ['<rect width="300" height="300" fill="#E9DCCB"/>', '<rect x="300" width="300" height="300" fill="#F7F3EC"/>',
         '<path d="M300,0 V300" stroke="#fff" stroke-width="6"/>']
    b.append(torso(BOSSY, 140, 200, 150, 110))
    b.append(arm(BOSSY, [(200, 225), (240, 200), (285, 182)], "point"))
    b.append(head(BOSSY, 140, 128, 60, eye="dot", brow="angry", mouth_kind="yell", look=1.5))
    b.append('<path d="M228,80 l14,-10 M236,98 l18,-3 M232,114 l16,6" stroke="#E5484D" stroke-width="4" stroke-linecap="round"/>')
    # the robot at the table, with its salad
    b.append(robot(455, 120, 1.0, eyes_kind="huh", mouth_kind="flat"))
    b.append(f'<rect x="310" y="236" width="290" height="64" fill="#ffffff" stroke="{INK}" stroke-width="{SW}"/>')
    b.append(f'<ellipse cx="395" cy="238" rx="56" ry="13" {_o("#ffffff")}/>'
             '<circle cx="380" cy="230" r="10" fill="#7cc36a"/><circle cx="396" cy="226" r="11" fill="#5fae4f"/>'
             '<circle cx="412" cy="231" r="9" fill="#9bd47f"/><circle cx="402" cy="234" r="5" fill="#E5484D"/>')
    b.append(f'<text x="540" y="70" font-family="Arial,Helvetica,sans-serif" font-weight="900" font-size="36" fill="{INK}">?</text>')
    return svg(600, 300, "".join(b), "#E9DCCB")


def pigeon():
    """The "is this a...?" layout: pointing at a butterfly, getting it wrong."""
    b = ['<rect width="600" height="330" fill="#BFD7EA"/>', '<rect y="250" width="600" height="80" fill="#9FB98A"/>']
    b.append(torso(DEV, 170, 215, 160, 120))
    b.append(arm(DEV, [(240, 240), (300, 210), (360, 190)], "open"))
    b.append(head(DEV, 160, 150, 60, eye="big", brow="up", mouth_kind="o", look=1.6))
    # the butterfly
    bx, by = 480, 120
    b.append(f'<g transform="rotate(-12 {bx} {by})">'
             f'<path d="M{bx},{by} C{bx - 70},{by - 90} {bx - 95},{by - 10} {bx - 8},{by + 6}z" fill="#FF9F43" stroke="{INK}" stroke-width="{SW}"/>'
             f'<path d="M{bx},{by} C{bx + 70},{by - 90} {bx + 95},{by - 10} {bx + 8},{by + 6}z" fill="#FF9F43" stroke="{INK}" stroke-width="{SW}"/>'
             f'<path d="M{bx},{by + 4} C{bx - 55},{by + 20} {bx - 50},{by + 70} {bx - 4},{by + 22}z" fill="#FFD25E" stroke="{INK}" stroke-width="{SW}"/>'
             f'<path d="M{bx},{by + 4} C{bx + 55},{by + 20} {bx + 50},{by + 70} {bx + 4},{by + 22}z" fill="#FFD25E" stroke="{INK}" stroke-width="{SW}"/>'
             f'<circle cx="{bx - 40}" cy="{by - 30}" r="9" fill="#fff"/><circle cx="{bx + 40}" cy="{by - 30}" r="9" fill="#fff"/>'
             f'<rect x="{bx - 5}" y="{by - 18}" width="10" height="50" rx="5" fill="{INK}"/>'
             f'<path d="M{bx - 2},{by - 18} q-8,-18 -18,-22 M{bx + 2},{by - 18} q8,-18 18,-22" fill="none" stroke="{INK}" stroke-width="2.5"/></g>')
    return svg(600, 330, "".join(b), "#BFD7EA")


def panik():
    p = DEV
    b = [arm(p, [(40, 150), (48, 112)]), arm(p, [(160, 150), (152, 112)]),
         head(p, 100, 78, 52, eye="big", brow="worried", mouth_kind="O", sweat=True)]
    return svg(200, 150, "".join(b), "#FF8A80")


def kalm():
    p = DEV
    b = [head(p, 100, 78, 52, eye="closed", brow="flat", mouth_kind="smile", blush=True),
         '<path d="M150,30 q8,-10 16,0 M162,48 q6,-8 12,0" fill="none" stroke="#2FA37C" stroke-width="3" stroke-linecap="round"/>']
    return svg(200, 150, "".join(b), "#B9F6CA")


SCENES = {"nope": nope, "yep": yep, "distracted": distracted, "fine": fine, "buttons": buttons,
          "brain1": lambda: brain(1), "brain2": lambda: brain(2), "brain3": lambda: brain(3), "brain4": lambda: brain(4),
          "yelling": yelling, "pigeon": pigeon, "panik": panik, "kalm": kalm}
SIZES = {name: tuple(int(v) for v in f().split('viewBox="0 0 ')[1].split('"')[0].split()) for name, f in SCENES.items()}

EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"


def draw(out: str | Path = Path(__file__).resolve().parent.parent / "templates" / "memes") -> None:
    """Save every scene as a PNG at twice its size (sharp on phones)."""
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        for name, scene in SCENES.items():
            w, h = SIZES[name]
            page = Path(tmp) / f"{name}.html"
            page.write_text(f'<!doctype html><style>html,body{{margin:0;overflow:hidden}}</style>{scene()}', encoding="utf-8")
            for attempt in range(3):  # headless Edge now and then hangs: try again with a fresh profile
                try:
                    subprocess.run([EDGE, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--force-device-scale-factor=2",
                                    f"--user-data-dir={Path(tmp) / f'profile{attempt}'}", f"--window-size={w},{h}",
                                    f"--screenshot={out / (name + '.png')}", page.as_uri()], check=True, capture_output=True, timeout=60)
                    break
                except subprocess.TimeoutExpired:
                    if attempt == 2:
                        raise
            print(name, w, h)


if __name__ == "__main__":
    draw()
