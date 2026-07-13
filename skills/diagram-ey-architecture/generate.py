#!/usr/bin/env python3
"""EY layered "Systems of…" architecture diagram generator (draw.io).

Emits a dark-theme, EY-branded capability stack:
  CONSUME (Engagement + Insight) · ENABLEMENT LAYER (yellow hero) ·
  CONNECT (Systems of Record) · RUN (Foundation), framed by a Systems of Trust
  L-rail (left + base) and a Systems of Innovation rail, with a Business
  Outcomes banner and upward value-flow arrows.

Variants:
    python3 generate.py capability             # icon in every capability box
    python3 generate.py layer                  # one icon per band header + rails
    python3 generate.py capability transparent # no background rect (for -t export)
    python3 generate.py layer transparent

Render / export with the `diagram-render-drawio` skill, e.g.
    DRAWIO="/Applications/draw.io.app/Contents/MacOS/draw.io"
    "$DRAWIO" -x -f svg         -o out.svg  in.drawio              # vector (transparent)
    "$DRAWIO" -x -t -f png -s 4  -o out.png  in-transparent.drawio # transparent 4x

Retarget for a different client by editing the CONTENT section near the bottom
(the CONSUME / PILLARS / CONNECT / RUN lists and the TITLE / H_* / *RAIL /
OUTCOMES / BASEBAND strings). Icons come from icons.py (keep it alongside).
"""
import sys
from icons import datauri

# --- output -------------------------------------------------------------------
OUTDIR = "diagrams/drawio"
BASENAME = "enablement-architecture"

# --- EY palette ---------------------------------------------------------------
BG="#1A1A24"; CARD="#2E2E38"; CARDS="#45454F"; PILL="#232330"; PILLS="#3A3A48"
YELLOW="#FFE600"; YELLOWS="#CDB800"; HDR="#25252F"; TRUST="#1F3864"; TRUSTS="#2A4A7F"
INNOV="#27ACAA"; INNOVS="#1E8987"; CHARCOAL="#2E2E38"; INK="#06302F"

# --- layout -------------------------------------------------------------------
W, H = 1600, 876
COLS = [206, 447, 688, 929, 1170]      # 5-column grid, each 224 wide
CW = 224
RUNCOLS = [(206, 384), (607, 384), (1008, 386)]


def esc(s):
    """Literal '&' must be double-escaped for html=1 labels (XML then HTML)."""
    return s.replace("&", "&amp;amp;")


def icon(cid, name, x, y, size, color=YELLOW):
    return (f'<mxCell id="{cid}" value="" style="shape=image;imageAspect=0;'
            f'image={datauri(name, color)};html=1;" vertex="1" parent="1">'
            f'<mxGeometry x="{x}" y="{y}" width="{size}" height="{size}" as="geometry"/></mxCell>')


def card(cid, x, y, w, h, title, desc, icn=None, stroke=CARDS):
    valign = "top;spacingTop=36" if icn else "middle"
    val = f'&lt;b&gt;{esc(title)}&lt;/b&gt;&lt;br&gt;&lt;font color=&quot;#B8B8C4&quot;&gt;{esc(desc)}&lt;/font&gt;'
    cells = [f'<mxCell id="{cid}" value="{val}" style="rounded=1;whiteSpace=wrap;html=1;'
             f'fillColor={CARD};strokeColor={stroke};fontColor=#FFFFFF;fontSize=12;align=center;'
             f'verticalAlign={valign};arcSize=10;" vertex="1" parent="1">'
             f'<mxGeometry x="{x}" y="{y}" width="{w}" height="{h}" as="geometry"/></mxCell>']
    if icn:
        cells.append(icon(cid + "_i", icn, x + w / 2 - 13, y + 8, 26))
    return cells


def pillar(cid, x, title, sub, sub_color, b1, b2, icn=None, title_color=None, stroke=PILLS):
    t = (f'&lt;b&gt;&lt;font color=&quot;{title_color}&quot;&gt;{esc(title)}&lt;/font&gt;&lt;/b&gt;'
         if title_color else f'&lt;b&gt;{esc(title)}&lt;/b&gt;')
    val = (f'{t}&lt;br&gt;&lt;font color=&quot;{sub_color}&quot;&gt;{esc(sub)}&lt;/font&gt;'
           f'&lt;br&gt;&lt;br&gt;&lt;font style=&quot;font-size:9px&quot;&gt;• {esc(b1)}&lt;br&gt;• {esc(b2)}&lt;/font&gt;')
    spacing = 40 if icn else 10
    cells = [f'<mxCell id="{cid}" value="{val}" style="rounded=1;whiteSpace=wrap;html=1;'
             f'fillColor={PILL};strokeColor={stroke};fontColor=#FFFFFF;fontSize=13;align=center;'
             f'verticalAlign=top;arcSize=12;spacingTop={spacing};" vertex="1" parent="1">'
             f'<mxGeometry x="{x}" y="332" width="{CW}" height="150" as="geometry"/></mxCell>']
    if icn:
        cells.append(icon(cid + "_i", icn, x + CW / 2 - 13, 340, 26))
    return cells


def hdr(cid, x, y, w, value, icn=None):
    spacing = 44 if icn else 12
    cells = [f'<mxCell id="{cid}" value="{value}" style="rounded=0;whiteSpace=wrap;html=1;'
             f'fillColor={HDR};strokeColor=none;fontColor=#FFFFFF;fontSize=13;align=left;'
             f'verticalAlign=middle;spacingLeft={spacing};" vertex="1" parent="1">'
             f'<mxGeometry x="{x}" y="{y}" width="{w}" height="28" as="geometry"/></mxCell>']
    if icn:
        cells.append(icon(cid + "_i", icn, x + 12, y + 4, 20))
    return cells


# ============================ CONTENT (edit me) ===============================
CONSUME = [("c_bi","chart","Analytics & BI","Trusted insights, real time"),
           ("c_ai","ai","AI & Agents","Assist · automate · augment"),
           ("c_wf","workflow","Digital Workflows","End-to-end orchestration"),
           ("c_ba","apps","Business Applications","Purpose-built apps & extensions"),
           ("c_pc","partner","Partner & Customer","Collaboration & experiences")]

PILLARS = [("e_intg","integration","Integration","API-led connectivity","#CFCFDA",
            "Standard APIs · events","Adapters · decoupling",None,PILLS),
           ("e_orch","orchestration","Orchestration","Process & workflow","#CFCFDA",
            "Workflow engine · rules","RPA · human-in-the-loop",None,PILLS),
           ("e_data","data","Data Platform","Unified data foundation","#CFCFDA",
            "Ingestion · data products","MDM · semantic · lake / mesh",YELLOW,YELLOW),
           ("e_idg","identity","Identity & Governance","Enforces Systems of Trust","#7FE3E1",
            "IAM/SSO · zero trust · API security","Data governance · lineage · policy",None,INNOV),
           ("e_ps","platform","Platform Services","Common services at scale","#CFCFDA",
            "Observability · logging","DevOps / CI-CD · cost mgmt",None,PILLS)]

CONNECT = [("r_erp","erp","ERP · SAP S/4HANA","Finance · supply chain · mfg"),
           ("r_plm","plm","PLM / Engineering","Design · BOM · change · reqs"),
           ("r_mes","mes","MES / MOM","Production · quality · traceability"),
           ("r_ot","ot","OT / Shop Floor","Machines · sensors · edge"),
           ("r_leg","legacy","Legacy (to modernize)","Historical make-to-order systems")]

RUN = [("f_cloud","cloud","Cloud","Azure / AWS"),
       ("f_hyb","hybrid","Hybrid by design","Scalable · secure · available"),
       ("f_onprem","onprem","On-premises","Where needed")]

TITLE = ('One connected foundation that turns data into '
         '&lt;font color=&quot;#FFE600&quot;&gt;intelligence, automation and value&lt;/font&gt;')
OUTCOMES = ('&lt;b&gt;BUSINESS OUTCOMES&lt;/b&gt;&#160;&#160;·&#160;&#160;faster decisions&#160;·&#160;'
            'higher productivity&#160;·&#160;lower complexity&#160;·&#160;better compliance&#160;·&#160;scalable growth')
LEFTRAIL = '&lt;b&gt;SYSTEMS OF TRUST&lt;/b&gt;&lt;br&gt;&lt;br&gt;secure &amp;amp; compliant by design'
RIGHTRAIL = ('&lt;b&gt;SYSTEMS OF INNOVATION&lt;/b&gt;&lt;br&gt;&lt;br&gt;fast lane&lt;br&gt;&lt;br&gt;'
             'AI &amp;amp; agents · sandbox / PoC · low-code')
BASEBAND = ('&lt;b&gt;SYSTEMS OF TRUST&lt;/b&gt;&#160;&#160;·&#160;&#160;set as policy across every layer, '
            'enforced at control points in the Enablement Layer&#160;&#160;·&#160;&#160;Security · '
            'IAM / Zero Trust · Compliance · Data Residency · Change Control')
H_CONSUME = ('&lt;b&gt;Systems of Engagement + Insight&lt;/b&gt;&#160;&#160;·&#160;&#160;'
             '&lt;font color=&quot;#9A9AA8&quot;&gt;experiences that drive outcomes&lt;/font&gt;')
H_ENABLE = ('&lt;b&gt;ENABLEMENT LAYER&lt;/b&gt;&#160;&#160;·&#160;&#160;the digital backbone that makes '
            'everything work together&#160;&#160;&#160;·&#160;&#160;&#160;&lt;b&gt;RFQ FOCUS&lt;/b&gt;')
H_CONNECT = ('&lt;b&gt;Systems of Record&lt;/b&gt;&#160;&#160;·&#160;&#160;&lt;font color=&quot;#9A9AA8&quot;&gt;'
             'core systems &amp;amp; operational technology that retain their role&lt;/font&gt;')
H_RUN = ('&lt;b&gt;Foundation&lt;/b&gt;&#160;&#160;·&#160;&#160;&lt;font color=&quot;#9A9AA8&quot;&gt;'
         'resilient, scalable infrastructure&lt;/font&gt;')
# ============================================================================


def frame(mode, transparent=False):
    cap = mode == "capability"
    lay = mode == "layer"
    c = []
    if not transparent:
        c.append(f'<mxCell id="bg" value="" style="rounded=0;whiteSpace=wrap;html=1;fillColor={BG};strokeColor=none;" vertex="1" parent="1"><mxGeometry x="0" y="0" width="{W}" height="{H}" as="geometry"/></mxCell>')
    c.append(f'<mxCell id="title" value="{TITLE}" style="text;html=1;align=center;verticalAlign=middle;fontSize=24;fontStyle=1;fontColor=#FFFFFF;" vertex="1" parent="1"><mxGeometry x="40" y="20" width="1520" height="42" as="geometry"/></mxCell>')
    c.append(f'<mxCell id="outcomes" value="{OUTCOMES}" style="rounded=1;whiteSpace=wrap;html=1;fillColor={CARD};strokeColor={YELLOW};fontColor={YELLOW};fontSize=13;align=center;verticalAlign=middle;arcSize=20;" vertex="1" parent="1"><mxGeometry x="40" y="96" width="1520" height="38" as="geometry"/></mxCell>')

    c.append(f'<mxCell id="leftrail" value="{LEFTRAIL}" style="rounded=0;whiteSpace=wrap;html=1;fillColor={TRUST};strokeColor={TRUSTS};fontColor=#FFFFFF;fontSize=14;horizontal=0;align=center;verticalAlign=middle;" vertex="1" parent="1"><mxGeometry x="40" y="150" width="150" height="666" as="geometry"/></mxCell>')
    if lay:
        c.append(icon("leftrail_i", "trust", 40 + 75 - 14, 162, 28))
    c.append(f'<mxCell id="rightrail" value="{RIGHTRAIL}" style="rounded=0;whiteSpace=wrap;html=1;fillColor={INNOV};strokeColor={INNOVS};fontColor={INK};fontSize=14;horizontal=0;align=center;verticalAlign=middle;" vertex="1" parent="1"><mxGeometry x="1410" y="150" width="150" height="626" as="geometry"/></mxCell>')
    if lay:
        c.append(icon("rightrail_i", "innovation", 1410 + 75 - 14, 162, 28, INK))

    c += hdr("consumeHdr", 206, 150, 1188, H_CONSUME, icn=("chart" if lay else None))
    for i, (cid, ic, t, d) in enumerate(CONSUME):
        c += card(cid, COLS[i], 182, CW, 86, t, d, icn=(ic if cap else None))

    c.append(f'<mxCell id="enableBox" value="" style="rounded=1;whiteSpace=wrap;html=1;fillColor={YELLOW};strokeColor={YELLOWS};arcSize=4;" vertex="1" parent="1"><mxGeometry x="200" y="284" width="1200" height="216" as="geometry"/></mxCell>')
    en_spacing = 36 if lay else 4
    c.append(f'<mxCell id="enableHdr" value="{H_ENABLE}" style="text;html=1;align=left;verticalAlign=middle;fontSize=15;fontColor=#2E2E38;spacingLeft={en_spacing};" vertex="1" parent="1"><mxGeometry x="212" y="290" width="1176" height="30" as="geometry"/></mxCell>')
    if lay:
        c.append(icon("enableHdr_i", "hub", 212, 292, 24, CHARCOAL))
    for i, (cid, ic, t, sub, sc, b1, b2, tc, st) in enumerate(PILLARS):
        c += pillar(cid, COLS[i], t, sub, sc, b1, b2, icn=(ic if cap else None), title_color=tc, stroke=st)

    c += hdr("connectHdr", 206, 520, 1188, H_CONNECT, icn=("data" if lay else None))
    for i, (cid, ic, t, d) in enumerate(CONNECT):
        c += card(cid, COLS[i], 552, CW, 86, t, d, icn=(ic if cap else None))

    c += hdr("runHdr", 206, 658, 1188, H_RUN, icn=("onprem" if lay else None))
    for i, (cid, ic, t, d) in enumerate(RUN):
        x, w = RUNCOLS[i]
        c += card(cid, x, 690, w, 70, t, d, icn=(ic if cap else None))

    c.append(f'<mxCell id="baseband" value="{BASEBAND}" style="rounded=0;whiteSpace=wrap;html=1;fillColor={TRUST};strokeColor={TRUSTS};fontColor=#FFFFFF;fontSize=12;align=center;verticalAlign=middle;" vertex="1" parent="1"><mxGeometry x="40" y="776" width="1520" height="40" as="geometry"/></mxCell>')

    for j, (ay, ah) in enumerate([(269, 12), (503, 14), (640, 14)]):
        c.append(f'<mxCell id="arrow{j}" value="" style="triangle;whiteSpace=wrap;html=1;fillColor={YELLOW};strokeColor=none;direction=north;" vertex="1" parent="1"><mxGeometry x="789" y="{ay}" width="22" height="{ah}" as="geometry"/></mxCell>')
    return c


def emit(mode, path, transparent=False):
    cells = frame(mode, transparent)
    xml = ('<mxfile host="app.diagrams.net"><diagram id="ey" name="EY Architecture">'
           f'<mxGraphModel dx="{W}" dy="{H}" grid="0" gridSize="10" guides="1" tooltips="1" '
           f'connect="1" arrows="1" fold="1" page="1" pageScale="1" pageWidth="{W}" pageHeight="{H}" '
           f'math="0" shadow="0"><root><mxCell id="0"/><mxCell id="1" parent="0"/>'
           + "".join(cells) + "</root></mxGraphModel></diagram></mxfile>")
    open(path, "w").write(xml)
    print("wrote", path)


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "capability"
    transparent = len(sys.argv) > 2 and sys.argv[2] == "transparent"
    suffix = "-transparent" if transparent else ""
    if mode in ("capability", "layer"):
        emit(mode, f"{OUTDIR}/{BASENAME}-icons-{mode}{suffix}.drawio", transparent)
    else:
        print("unknown mode:", mode, "(use: capability | layer [transparent])")
