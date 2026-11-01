<p align="center"><img src="assets/brand/icon.svg" width="128" height="128" alt="Helios"></p>

# Helios - Solar Position and Events for Home Assistant

**Version:** `0.3.2`

*Read this in: [English](#english-documentation) | [Français](#documentation-française)*

---

<a name="english-documentation"></a>

## English Documentation

**Helios** is a lightweight, pure-Python Home Assistant custom integration that calculates solar position and daily solar events from established astronomical equations (see the [mathematical reference](#mathematical-reference--equations-audit)).

### Key Features

* **Pure Python:** Helios and its only requirement, astraeos-astro, use nothing but the Python standard library. There is no compiled code, and Home Assistant installs the requirement by itself.
* **PyEphem Accuracy:** The Sun's position comes from [astraeos-astro](https://github.com/astraeos-dev/astraeos-astro), a pure-Python port of libastro, the C core of PyEphem, published on PyPI. It matches PyEphem to 0.001″.
* **Decoupled Architecture:** `solar_engine.py` has zero Home Assistant imports, making unit testing and equation auditing effortless.
* **Complete Solar Metrics:** Azimuth, apparent and geometric elevation, declination, right ascension (degrees and h m s), equation of time, Earth-Sun distance (AU and km), the constellation the Sun is in, Julian Day, solar noon and midnight, sunrise/sunset, civil/nautical/astronomical twilights, and blue and golden hours, each with the Sun's azimuth at that time.

### Installation

Helios requires Home Assistant 2025.4 or later.

1. **Via HACS:** Add `https://github.com/astraeos-dev/Helios` as a custom repository (category *Integration*), then install **Helios**, or use this button:

   [![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=astraeos-dev&repository=Helios&category=integration)

2. **Manual:** Copy the `custom_components/astraeos_helios` folder into the `custom_components/` directory of your Home Assistant configuration, then restart Home Assistant.
3. Go to **Settings -> Devices & services -> Add integration** and search for **Helios**.

The elevation (−500 to 9000 m) and the update interval (10 to 3600 seconds, 60 by default) can be changed later from the integration options. Elevation lowers the visible horizon, so the Sun rises earlier and sets later; set it to 0 to get almanac times.

The update interval paces the position sensors (azimuth, elevation…). Binary sensors and the daily timestamps do not wait for it: Helios also refreshes one second after each event that changes them.

### Entities

| Entity | Unit | Notes |
| --- | --- | --- |
| Azimuth | ° | 0° = North, 90° = East |
| Apparent elevation | ° | Includes atmospheric refraction |
| True geometric elevation | ° | Diagnostic, without refraction |
| Declination | ° | |
| Right ascension | ° | Diagnostic; `hms` attribute in hours, minutes and seconds, such as `13h 13m 31.4s` |
| Equation of time | min | Apparent minus mean solar time |
| Distance | AU | Earth-Sun distance, diagnostic; `distance_km` attribute in kilometres |
| Constellation | | The constellation the Sun is in, among the 13 it crosses, Ophiuchus included |
| Daylight duration | min | Time the Sun spends above the horizon during the solar day |
| Julian Day | | Diagnostic |
| Solar noon, Sunrise, Sunset | timestamp | |
| Solar midnight | timestamp | End of the solar day, when the Sun is at its lowest |
| Civil dawn, Civil dusk | timestamp | |
| Nautical and Astronomical dawn/dusk | timestamp | Diagnostic |
| Blue and golden hour starts and ends | timestamp | Diagnostic, see [Blue and Golden Hours](#blue-and-golden-hours) |
| Sun above horizon | on/off | On between sunrise and sunset |
| Golden hour, Blue hour | on/off | On during the morning and evening golden or blue hour |

Every timestamp has an `azimuth` attribute: the Sun's azimuth when the event happens (0° = North, 90° = East), such as where it rises or sets.

### Daily Events and the Solar Day

Timestamps describe the current **solar day**, which runs from one solar midnight (about 12 hours from solar noon, when the Sun is at its lowest) to the next, rather than the civil date. Every dawn and dusk happens while it is displayed, so time triggers on these sensors fire, including for a sunset or a dusk after midnight (Reykjavik in June, astronomical dusk in Western Europe in summer). Between civil midnight and solar midnight, the sensors still show the previous day's events.

The solar day only depends on longitude, which also keeps the right day where the time zone is a day away from it, such as Samoa or Kiribati (UTC+13/+14).

A timestamp is `unknown` when the event does not happen that day: polar day or night, or summer nights that never get dark enough for a twilight.

### Blue and Golden Hours

The blue hour runs from civil twilight (Sun at $-6^\circ$) to $-4^\circ$, and the golden hour from $-4^\circ$ to $+6^\circ$. These are photographic conventions rather than astronomical standards; like twilights, they apply to the geometric altitude and do not depend on elevation. Four sensors mark their bounds, along with civil dawn and dusk:

| Period | Start | End |
| --- | --- | --- |
| Morning blue hour | Civil dawn | Morning blue hour end |
| Morning golden hour | Morning blue hour end | Morning golden hour end |
| Evening golden hour | Evening golden hour start | Evening blue hour start |
| Evening blue hour | Evening blue hour start | Civil dusk |

The *Golden hour* and *Blue hour* binary sensors are on during these periods, morning and evening. The timestamps are `unknown` on days without the matching crossing, but the binary sensors still follow the Sun: at high latitudes, it can stay above $-4^\circ$ through summer nights (no blue hour) and below $+6^\circ$ through winter days (golden hour all day long).

### Mathematical Reference & Equations Audit

The Sun's position comes from the astraeos-astro library (section 2). Daily events, refraction and the remaining formulas follow **Jean Meeus, *Astronomical Algorithms*, 2nd Edition (1998)**:

#### 1. Julian Day ($JD$) and Julian Century ($T$) — *Chapter 7 (Eq. 7.1) & Chapter 25 (Eq. 25.1)*

For a given UTC date $(Y, M, D)$ with decimal day $D$ (if $M \le 2$, $Y \leftarrow Y-1$ and $M \leftarrow M+12$):

$$
A = \lfloor Y / 100 \rfloor, \quad B = 2 - A + \lfloor A / 4 \rfloor
$$

$$
JD = \lfloor 365.25 (Y + 4716) \rfloor + \lfloor 30.6001 (M + 1) \rfloor + D + B - 1524.5
$$

$$
T = \frac{JD - 2451545.0}{36525}
$$

#### 2. Position of the Sun — *astraeos-astro, ported from libastro*

[astraeos-astro](https://github.com/astraeos-dev/astraeos-astro), published on PyPI, is a pure-Python port of the parts of libastro, the C library at the heart of PyEphem, that place the Sun (MIT license). It started in Helios and now has its own repository, where its tests compare it with PyEphem and a script generates its data tables from libastro's sources.

| Step | Method |
| --- | --- |
| Time scales | $\Delta T$ = TT − UT: Astronomical Almanac table from 1620 to 2018, Morrison and Stephenson (2004) before, extrapolated after |
| The Earth around the Sun | VSOP87D as truncated in libastro (406 terms), reduced to FK5 |
| Nutation and obliquity | IAU 1980 nutation (106 terms) and mean obliquity |
| Apparent place | Ecliptic to equator, nutation, annual aberration |
| Sidereal time | IAU 1982 Greenwich mean sidereal time plus the equation of the equinoxes |
| Observer | Parallax on the Earth's ellipsoid, then altitude and azimuth |
| Constellation | IAU boundaries (Delporte 1930) at the B1875.0 equinox, method of Roman (1987) |

Against PyEphem 4.2.1 over 3,000 random moments and places from 1900 to 2100: the same $\Delta T$, apparent right ascension and declination within 0.001″, altitude and azimuth within 0.05″ (PyEphem stores them in single precision), distance within $10^{-7}$ AU, and the same constellation. Daily events fall within 0.25 s of PyEphem's.

The mean elements kept as diagnostics follow Chapter 25: $L_0$, $M$ and $e$ from Eq. 25.2 to 25.4, the equation of the center as $C = \odot - L_0$, and the apparent longitude $\odot + \Delta\psi - 20.4898''/R$ (Eq. 25.10).

#### 3. Equation of Time ($E$) — *Chapter 28 (Eq. 28.1 and 28.2)*

With $\tau$ in Julian millennia of TT from J2000.0 and $L_0$ the Sun's mean longitude referred to the mean equinox of date:

$$
L_0 = 280.4664567^\circ + 360007.6982779^\circ\tau + 0.03032028^\circ\tau^2 + \frac{\tau^3}{49931} - \frac{\tau^4}{15300} - \frac{\tau^5}{2000000}
$$

$$
E = L_0 - 0.0057183^\circ - \alpha + \Delta\psi\cos\varepsilon
$$

#### 4. Atmospheric Refraction — *Chapter 16 (Saemundsson's Formula, Eq. 16.4)*

$$
R_{\text{arcmin}} = \frac{1.02}{\tan\left(h_0 + \frac{10.3}{h_0 + 5.11}\right)}, \quad h_{\text{apparent}} = h_0 + \frac{R_{\text{arcmin}}}{60}
$$

Saemundsson's formula is not valid below about $-1^\circ$. Under that limit, refraction decays as $1/\tan(h_0)$ (the form NOAA uses below the horizon), matched at $-1^\circ$ so the apparent elevation stays continuous:

$$
R(h_0) = R(-1^\circ)\,\frac{\tan(1^\circ)}{\tan(-h_0)} \quad \text{for } h_0 < -1^\circ
$$

#### 5. Rising, Transit and Setting — *Chapter 15 (Eq. 15.1)*

* **Solar Noon and Solar Midnight:** the Sun crosses the meridian when apparent solar time is 12:00 ($H = 0^\circ$) and is at its lowest at 24:00 ($H = 180^\circ$). In minutes from 0h UTC, with $E$ refined at the event:

  $$
  t_{\text{noon}} = 720 - 4L_{\text{east}} - E, \quad t_{\text{midnight}} = 1440 - 4L_{\text{east}} - E
  $$
* **Hour Angle of Sunrise, Sunset, Twilights, Blue and Golden Hours ($H_0$, Eq. 15.1):**

  $$
  \cos(H_0) = \frac{\sin(h_{\text{target}}) - \sin(\phi)\sin(\delta)}{\cos(\phi)\cos(\delta)}
  $$

  Where $h_{\text{target}}$ is $-0.8333^\circ$ (sunrise/sunset), $-6^\circ$ (civil), $-12^\circ$ (nautical), $-18^\circ$ (astronomical), and $-4^\circ$ and $+6^\circ$ (blue and golden hours). Thresholds apply to the geometric altitude $h_0$; the sunrise/sunset one already includes refraction and the solar semi-diameter, so *Sun above horizon* compares $h_0$ against it as well.

  For an observer at elevation $h$ (meters), the sunrise/sunset threshold is lowered by the dip of the visible horizon, $1.76'\sqrt{h}$ (almanac approximation, terrestrial refraction included; Chapter 15 assumes $h = 0$). Twilights, blue and golden hours are defined against the astronomical horizon and do not change.

  Each time found from the equation of time can be a few seconds off the Sun's actual position. It is then corrected with that position (p. 103) until the correction falls under 10 ms, so binary sensors switch at the times shown:

  $$
  \Delta m = -\frac{H}{360^\circ} \ \text{(transits)}, \quad \Delta m = \frac{h_0 - h_{\text{target}}}{360^\circ\cos(\delta)\cos(\phi)\sin(H)} \ \text{(other events)}
  $$
* **Daylight Duration:** sunset minus sunrise. On days without one of them (around the midnight sun), the matching solar midnight, taken as solar noon $\pm$ 12 h, bounds the daylight instead.
* **Constellation:** the Sun's mean position of date, precessed to B1875.0 and looked up in the IAU boundary table (section 2). The sensor shows the 13 constellations along the ecliptic.

---

<a name="documentation-française"></a>

## Documentation Française

**Helios** est une intégration personnalisée pour Home Assistant, en Python pur, qui calcule la position du soleil et les heures solaires quotidiennes à partir d'équations astronomiques éprouvées (voir les [références des équations](#références-des-équations-pour-vérification)).

### Caractéristiques principales

* **Python pur :** Helios et sa seule dépendance, astraeos-astro, n'utilisent que la bibliothèque standard de Python. Il n'y a aucun code compilé, et Home Assistant installe cette dépendance tout seul.
* **Précision de PyEphem :** La position du soleil vient de [astraeos-astro](https://github.com/astraeos-dev/astraeos-astro), un portage en Python pur de libastro, le cœur en C de PyEphem, publié sur PyPI. Il donne les mêmes valeurs que PyEphem à 0,001″ près.
* **Maintenance simplifiée :** Le fichier `solar_engine.py` est totalement indépendant de Home Assistant. Vous pouvez le tester ou le modifier directement avec Python.
* **Données complètes :** Azimut, élévation apparente et géométrique vraie, déclinaison, ascension droite (en degrés et en h m s), équation du temps, distance Terre-Soleil (en UA et en km), constellation où se trouve le soleil, Jour Julien, midi et minuit solaires, lever/coucher du soleil, crépuscules civil, nautique et astronomique, heures bleue et dorée, chacun avec l'azimut du soleil à ce moment.

### Installation

Helios nécessite Home Assistant 2025.4 ou plus récent.

1. **Via HACS :** Ajoutez `https://github.com/astraeos-dev/Helios` en tant que dépôt personnalisé (*Custom Repository*, catégorie *Integration*), puis installez **Helios**, ou utilisez ce bouton :

   [![Ouvrir le dépôt dans le Home Assistant Community Store de votre instance Home Assistant.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=astraeos-dev&repository=Helios&category=integration)

2. **Manuelle :** Copiez le dossier `custom_components/astraeos_helios` dans le répertoire `custom_components/` de votre configuration Home Assistant, puis redémarrez Home Assistant.
3. Allez dans **Paramètres -> Appareils et services -> Ajouter une intégration** et recherchez **Helios**.

L'altitude (de −500 à 9000 m) et l'intervalle de mise à jour (de 10 à 3600 secondes, 60 par défaut) se modifient ensuite dans les options de l'intégration. L'altitude abaisse l'horizon visible : le soleil se lève plus tôt et se couche plus tard. Mettez 0 pour retrouver les heures des éphémérides.

L'intervalle de mise à jour rythme les capteurs de position (azimut, élévation…). Les capteurs binaires et les horodatages du jour ne l'attendent pas : Helios se met aussi à jour une seconde après chaque événement qui les change.

### Entités

| Entité | Unité | Remarques |
| --- | --- | --- |
| Azimut | ° | 0° = Nord, 90° = Est |
| Élévation apparente | ° | Inclut la réfraction atmosphérique |
| Élévation géométrique vraie | ° | Diagnostic, sans réfraction |
| Déclinaison | ° | |
| Ascension droite | ° | Diagnostic ; attribut `hms` en heures, minutes et secondes, par exemple `13h 13m 31.4s` |
| Équation du temps | min | Temps solaire vrai moins temps solaire moyen |
| Distance | UA | Distance Terre-Soleil, diagnostic ; attribut `distance_km` en kilomètres |
| Constellation | | Constellation où se trouve le soleil, parmi les 13 qu'il traverse, Ophiuchus compris |
| Durée du jour | min | Temps passé par le soleil au-dessus de l'horizon pendant la journée solaire |
| Jour Julien | | Diagnostic |
| Midi solaire, Lever du soleil, Coucher du soleil | horodatage | |
| Minuit solaire | horodatage | Fin de la journée solaire, quand le soleil est au plus bas |
| Aube civile, Crépuscule civil | horodatage | |
| Aubes et crépuscules nautiques et astronomiques | horodatage | Diagnostic |
| Débuts et fins des heures bleue et dorée | horodatage | Diagnostic, voir [Heures bleue et dorée](#heures-bleue-et-dorée) |
| Soleil au-dessus de l'horizon | on/off | Allumé entre le lever et le coucher |
| Heure dorée, Heure bleue | on/off | Allumés pendant l'heure dorée ou bleue, du matin comme du soir |

Chaque horodatage a un attribut `azimuth` : l'azimut du soleil au moment de l'événement (0° = Nord, 90° = Est), par exemple l'endroit où il se lève ou se couche.

### Événements quotidiens et journée solaire

Les horodatages décrivent la **journée solaire** en cours, qui va d'un minuit solaire (environ 12 heures après le midi solaire, quand le soleil est au plus bas) au suivant, et non la date civile. Chaque aube et chaque crépuscule a lieu pendant qu'il est affiché : les déclencheurs horaires sur ces capteurs se déclenchent donc, y compris pour un coucher ou un crépuscule après minuit (Reykjavik en juin, crépuscule astronomique en Europe de l'Ouest l'été). Entre le minuit civil et le minuit solaire, les capteurs affichent encore les événements de la veille.

La journée solaire ne dépend que de la longitude, ce qui garde aussi le bon jour là où le fuseau horaire en est éloigné d'une journée, comme aux Samoa ou à Kiribati (UTC+13/+14).

Un horodatage vaut `unknown` quand l'événement n'a pas lieu ce jour-là : jour ou nuit polaire, ou nuits d'été jamais assez sombres pour un crépuscule.

### Heures bleue et dorée

L'heure bleue va du crépuscule civil (soleil à $-6^\circ$) à $-4^\circ$, l'heure dorée de $-4^\circ$ à $+6^\circ$. Ce sont des conventions photographiques et non des définitions astronomiques ; comme les crépuscules, elles portent sur la hauteur géométrique et ne dépendent pas de l'altitude. Quatre capteurs marquent leurs limites, avec l'aube et le crépuscule civils :

| Période | Début | Fin |
| --- | --- | --- |
| Heure bleue du matin | Aube civile | Fin de l'heure bleue du matin |
| Heure dorée du matin | Fin de l'heure bleue du matin | Fin de l'heure dorée du matin |
| Heure dorée du soir | Début de l'heure dorée du soir | Début de l'heure bleue du soir |
| Heure bleue du soir | Début de l'heure bleue du soir | Crépuscule civil |

Les capteurs binaires *Heure dorée* et *Heure bleue* sont allumés pendant ces périodes, le matin comme le soir. Les horodatages valent `unknown` les jours sans le passage correspondant, mais les capteurs binaires suivent toujours le soleil : aux hautes latitudes, il peut rester au-dessus de $-4^\circ$ les nuits d'été (pas d'heure bleue) et sous $+6^\circ$ les jours d'hiver (heure dorée toute la journée).

### Références des équations pour vérification

La position du soleil vient de la bibliothèque astraeos-astro (point 2). Les événements quotidiens, la réfraction et les autres formules suivent l'ouvrage **Jean Meeus, *Astronomical Algorithms*, 2nd Edition (1998)** :

1. **Jour Julien ($JD$) et Siècle Julien ($T$) :** Chapitre 7 (Éq. 7.1, p. 61) et Chapitre 25 (Éq. 25.1, p. 163).
2. **Position du soleil :** bibliothèque [astraeos-astro](https://github.com/astraeos-dev/astraeos-astro), publiée sur PyPI, un portage en Python pur des parties de libastro, la bibliothèque C au cœur de PyEphem, qui placent le soleil (licence MIT). Née dans Helios, elle a désormais son propre dépôt, où ses tests la comparent à PyEphem et un script génère ses tables depuis les sources de libastro. Elle enchaîne $\Delta T$ = TT − UT (table de l'Astronomical Almanac de 1620 à 2018, Morrison et Stephenson 2004 avant, extrapolation après), la position de la Terre autour du soleil par VSOP87D tronquée comme dans libastro (406 termes, ramenée au FK5), la nutation UAI 1980 (106 termes) et l'obliquité moyenne, le passage à l'équateur avec nutation et aberration annuelle, le temps sidéral (temps sidéral moyen de Greenwich UAI 1982 et équation des équinoxes), la parallaxe sur l'ellipsoïde terrestre, puis la hauteur et l'azimut. Comparé à PyEphem 4.2.1 sur 3 000 instants et lieux tirés au hasard de 1900 à 2100 : même $\Delta T$, ascension droite et déclinaison apparentes à 0,001″ près, hauteur et azimut à 0,05″ (PyEphem les stocke en simple précision), distance à $10^{-7}$ UA, même constellation ; les événements quotidiens tombent à moins de 0,25 s de ceux de PyEphem.
3. **Éléments moyens (diagnostic) :** Chapitre 25 (Éq. 25.2 à 25.4, p. 163) pour $L_0$, $M$ et $e$, avec l'équation du centre $C = \odot - L_0$ et la longitude apparente $\odot + \Delta\psi - 20.4898''/R$ (Éq. 25.10).
4. **Réfraction atmosphérique ($R$) :** Chapitre 16 (Formule de Saemundsson, Éq. 16.4, p. 106). *Note : la formule n'est plus valable sous $-1^\circ$ environ ; en dessous, la réfraction décroît en $1/\tan(h_0)$ (forme utilisée par la NOAA sous l'horizon), raccordée à $-1^\circ$ pour que l'élévation apparente reste continue.*
5. **Équation du temps ($E$) :** Chapitre 28 (Éq. 28.1 et 28.2, p. 183) : $E = L_0 - 0.0057183^\circ - \alpha + \Delta\psi\cos\varepsilon$, où $L_0$ est la longitude moyenne du soleil rapportée à l'équinoxe moyen de la date.
6. **Lever, passage au méridien et coucher ($H_0$) :** Chapitre 15 (Éq. 15.1, p. 101-103) avec double itération pour affiner la déclinaison et l'équation du temps à l'instant exact de chaque événement. Chaque heure obtenue est ensuite corrigée avec la position du soleil à cet instant (p. 103), $\Delta m = -H/360^\circ$ pour un passage au méridien et $\Delta m = (h_0 - h_{\text{cible}})/(360^\circ\cos\delta\cos\phi\sin H)$ sinon, jusqu'à une correction inférieure à 10 ms : les capteurs binaires basculent aux heures affichées. Le soleil passe au méridien quand le temps solaire vrai vaut 12 h ($H = 0^\circ$) et au plus bas, au minuit solaire, quand il vaut 24 h ($H = 180^\circ$), soit $720 - 4L_{\text{est}} - E$ et $1440 - 4L_{\text{est}} - E$ minutes après 0 h UTC. Les seuils ($-0.8333^\circ$, $-6^\circ$, $-12^\circ$, $-18^\circ$, et $-4^\circ$ et $+6^\circ$ pour les heures bleue et dorée) portent sur la hauteur géométrique $h_0$ ; celui du lever et du coucher inclut déjà la réfraction et le demi-diamètre solaire, c'est donc aussi à lui que *Soleil au-dessus de l'horizon* compare $h_0$. Pour un observateur à l'altitude $h$ (en mètres), ce seuil est abaissé de la dépression de l'horizon visible, $1.76'\sqrt{h}$ (approximation des éphémérides nautiques, réfraction terrestre comprise ; le chapitre 15 suppose $h = 0$). Les crépuscules et les heures bleue et dorée, définis par rapport à l'horizon astronomique, ne changent pas.
7. **Durée du jour :** coucher moins lever. Les jours sans l'un des deux (autour du soleil de minuit), c'est le minuit solaire correspondant, pris à midi solaire $\pm$ 12 h, qui borne la durée.
8. **Constellation :** position moyenne du soleil à la date, précessée à l'équinoxe B1875.0 puis cherchée dans la table des frontières de l'UAI (Delporte 1930, méthode de Roman 1987, voir le point 2). Le capteur montre les 13 constellations de l'écliptique.
