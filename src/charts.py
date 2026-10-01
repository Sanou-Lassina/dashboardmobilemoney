"""Fabrique de graphiques Plotly à l'identité visuelle commune."""
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from . import config as C


def layout(fig, titre: str = "", h: int = 380, unifie: bool = False, legende_bas: bool = True):
    fig.update_layout(
        title=dict(text=titre, font=dict(size=15, color=C.BLEU), x=0.01),
        paper_bgcolor="white", plot_bgcolor="white", height=h,
        font=dict(family="Segoe UI, Arial, sans-serif", color="#1E2936"),
        margin=dict(l=40, r=20, t=55, b=40),
        legend=dict(orientation="h", y=-0.22) if legende_bas else dict(),
        hovermode="x unified" if unifie else "closest",
    )
    fig.update_xaxes(showgrid=False, zeroline=False)
    fig.update_yaxes(showgrid=True, gridcolor="#EEEEEE", zeroline=False)
    return fig


def couleur_taux(p) -> str:
    if p is None or pd.isna(p):
        return "#B0B7C3"
    return C.VERT if p >= C.SEUIL_VERT else (C.JAUNE if p >= C.SEUIL_ORANGE else C.ROUGE)


def barres_atteinte(df: pd.DataFrame, col: str, titre: str, h: int = 380):
    d = df.dropna(subset=[col])
    fig = go.Figure(go.Bar(x=d["Agence"], y=d[col], marker_color=[couleur_taux(v) for v in d[col]],
                           text=[f"{v:.1f} %" for v in d[col]], textposition="outside",
                           hovertemplate="<b>%{x}</b><br>%{y:.1f} %<extra></extra>"))
    fig.add_hline(y=100, line_dash="dash", line_color=C.BLEU, annotation_text="Objectif 100 %")
    fig.add_hline(y=80, line_dash="dot", line_color=C.JAUNE, annotation_text="Seuil 80 %")
    fig.update_yaxes(ticksuffix=" %", range=[0, max(120, float(d[col].max()) * 1.15) if len(d) else 120])
    fig.update_xaxes(tickangle=-25)
    return layout(fig, titre, h, legende_bas=False)


def serie_gtv(s: pd.DataFrame, gran: str, titre: str = "", h: int = 380):
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=s["Période"], y=s["GTV"], name="GTV (FCFA)", mode="lines",
                             line=dict(color=C.ORANGE, width=2.5), fill="tozeroy", fillcolor="rgba(255,107,44,0.12)"))
    fig.add_trace(go.Bar(x=s["Période"], y=s["Tx"], name="Transactions", yaxis="y2", marker_color="rgba(0,51,102,0.25)"))
    fig.update_layout(yaxis=dict(title="GTV (FCFA)"), yaxis2=dict(title="Transactions", overlaying="y", side="right", showgrid=False))
    fig.update_xaxes(type="category" if gran != "Jour" else "date")
    return layout(fig, titre, h, unifie=True)


def reel_vs_objectif(m: pd.DataFrame, titre: str = "", h: int = 380):
    """m : Période, CA, Objectif, Taux (agrégé sur le périmètre)."""
    fig = go.Figure()
    fig.add_trace(go.Bar(x=m["Période"], y=m["CA"], name="Réalisé", marker_color=[couleur_taux(t) for t in m["Taux"]],
                         customdata=m["Taux"], hovertemplate="%{x}<br>Réalisé : %{y:,.0f} FCFA<br>Atteinte : %{customdata:.1f} %<extra></extra>"))
    fig.add_trace(go.Scatter(x=m["Période"], y=m["Objectif"], name="Objectif", mode="lines+markers",
                             line=dict(color=C.BLEU, width=2, dash="dot"), marker_symbol="diamond"))
    fig.update_xaxes(type="category")
    return layout(fig, titre, h, unifie=True)


def waterfall(w: pd.DataFrame, titre: str = "", h: int = 400):
    fig = go.Figure(go.Waterfall(
        x=w["Étape"], y=w["Valeur"], measure=["absolute", "relative", "relative", "relative", "total"],
        connector=dict(line=dict(color="#B0B7C3")),
        increasing=dict(marker=dict(color=C.VERT)), decreasing=dict(marker=dict(color=C.ROUGE)),
        totals=dict(marker=dict(color=C.BLEU)),
        text=[f"{v / 1e6:,.1f} M".replace(",", " ") for v in w["Valeur"]], textposition="outside"))
    fig.update_yaxes(title="FCFA")
    return layout(fig, titre, h, legende_bas=False)


def pareto(p: pd.DataFrame, col_nom: str, col_val: str, titre: str = "", h: int = 400, max_barres: int = 40):
    d = p.head(max_barres)
    fig = go.Figure()
    fig.add_trace(go.Bar(x=d[col_nom], y=d[col_val], name=col_val, marker_color=C.ORANGE))
    fig.add_trace(go.Scatter(x=d[col_nom], y=d["Cumul_%"], name="Cumul (%)", yaxis="y2", mode="lines+markers",
                             line=dict(color=C.BLEU, width=2)))
    fig.add_trace(go.Scatter(x=d[col_nom], y=[80] * len(d), yaxis="y2", mode="lines", name="Seuil 80 %",
                             line=dict(color=C.ROUGE, width=1.5, dash="dot"), hoverinfo="skip"))
    fig.update_layout(yaxis2=dict(title="Cumul (%)", overlaying="y", side="right", range=[0, 105], showgrid=False))
    fig.update_xaxes(type="category", tickangle=-60, showticklabels=len(d) <= 25)
    return layout(fig, titre, h, unifie=False)


def matrice(mat: pd.DataFrame, titre: str = "", h: int = 380, echelle=None, fmt: str = ".0f", suffixe: str = ""):
    fig = px.imshow(mat, aspect="auto", color_continuous_scale=echelle or [[0, "white"], [0.5, C.JAUNE], [1, C.ORANGE]],
                    text_auto=fmt)
    fig.update_coloraxes(colorbar_title=suffixe)
    return layout(fig, titre, h, legende_bas=False)


def entonnoir(df: pd.DataFrame, titre: str = "", h: int = 360):
    fig = go.Figure(go.Funnel(y=df["Étape"], x=df["Clients"], textinfo="value+percent initial",
                              marker=dict(color=[C.BLEU, "#1F5C99", C.ORANGE, C.VERT][:len(df)])))
    return layout(fig, titre, h, legende_bas=False)


def carte(geo: pd.DataFrame, col_taille: str, col_couleur: str, titre: str = "", h: int = 460, echelle=None):
    d = geo.dropna(subset=["Latitude", "Longitude"]).copy()
    d[col_taille] = d[col_taille].clip(lower=0).fillna(0)
    args = dict(lat="Latitude", lon="Longitude", size=col_taille, color=col_couleur, hover_name="Agence",
                size_max=45, zoom=5, center=dict(lat=12.2, lon=-1.6),
                color_continuous_scale=echelle or [[0, C.VERT], [0.5, C.JAUNE], [1, C.ROUGE]])
    try:
        fig = px.scatter_map(d, map_style="open-street-map", **args)
    except AttributeError:  # Plotly < 5.24
        fig = px.scatter_mapbox(d, mapbox_style="open-street-map", **args)
    fig.update_layout(title=dict(text=titre, font=dict(size=15, color=C.BLEU), x=0.01), height=h,
                      margin=dict(l=0, r=0, t=50, b=0))
    return fig
