<p align="center"><img src="assets/brand/icon.svg" width="128" height="128" alt="Helios"></p>

# Helios - Solar Position and Events for Home Assistant

**Version:** `0.3.2`

*Read this in: [English](#english-documentation) | [Français](#documentation-française)*

---

<a name="english-documentation"></a>

## English Documentation

**Helios** is a lightweight, zero-dependency Home Assistant custom integration that calculates solar position and daily solar events from established astronomical equations (see the [mathematical reference](#mathematical-reference--equations-audit)).

### Key Features

* **Zero External Dependencies:** Uses exclusively Python's standard `math` and `datetime` libraries (`"requirements": []` in `manifest.json`).
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

All calculations implemented in `custom_components/astraeos_helios/solar_engine.py` can be verified against **Jean Meeus, *Astronomical Algorithms*, 2nd Edition (1998)**:

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

#### 2. Solar Coordinates — *Chapter 25 (Eq. 25.2 to 25.8)*

* **Geometric Mean Longitude of the Sun ($L_0$, Eq. 25.2):**
  $$
  L_0 = 280.46646^\circ + 36000.76983^\circ T + 0.0003032^\circ T^2 \pmod{360^\circ}
  $$
* **Mean Anomaly of the Sun ($M$, Eq. 25.3):**
  $$
  M = 357.52911^\circ + 35999.05029^\circ T - 0.0001537^\circ T^2 \pmod{360^\circ}
  $$
* **Eccentricity of Earth's Orbit ($e$, Eq. 25.4):**
  $$
  e = 0.016708634 - 0.000042037 T - 0.0000001267 T^2
  $$
* **Sun's Equation of the Center ($C$, p. 164):**
  $$
  C = (1.914602^\circ - 0.004817^\circ T - 0.000014^\circ T^2)\sin(M) + (0.019993^\circ - 0.000101^\circ T)\sin(2M) + 0.000289^\circ\sin(3M)
  $$
* **True Longitude ($\odot$), True Anomaly ($v$), and Earth-Sun Distance ($R$ in AU, Eq. 25.5):**
  $$
  \odot = L_0 + C, \quad v = M + C, \quad R = \frac{1.000001018(1 - e^2)}{1 + e\cos(v)}
  $$
* **Apparent Longitude ($\lambda$, Eq. 25.8):**
  $$
  \Omega = 125.04^\circ - 1934.136^\circ T, \quad \lambda = \odot - 0.00569^\circ - 0.00478^\circ\sin(\Omega)
  $$

#### 3. Obliquity of the Ecliptic & Equatorial Coordinates — *Chapter 22 (Eq. 22.2) & Chapter 25 (Eq. 25.6–25.8)*

* **Mean ($\varepsilon_0$) and Corrected Obliquity ($\varepsilon$):**

  $$
  \varepsilon_0 = 23^\circ 26' 21.448'' - 46.8150'' T - 0.00059'' T^2 + 0.001813'' T^3
  $$

  $$
  \varepsilon = \varepsilon_0 + 0.00256^\circ\cos(\Omega)
  $$
* **Right Ascension ($\alpha$, Eq. 25.6) and Declination ($\delta$, Eq. 25.7):**

  $$
  \tan(\alpha) = \frac{\cos(\varepsilon)\sin(\lambda)}{\cos(\lambda)}, \quad \sin(\delta) = \sin(\varepsilon)\sin(\lambda)
  $$

#### 4. Sidereal Time & Horizontal Coordinates (Azimuth & Elevation) — *Chapter 12 (Eq. 12.4) & Chapter 13 (Eq. 13.5–13.6)*

* **Mean Sidereal Time at Greenwich ($\theta_0$, Eq. 12.4):**

  $$
  \theta_0 = 280.46061837^\circ + 360.98564736629^\circ(JD - 2451545.0) + 0.000387933^\circ T^2 - \frac{T^3}{38710000}
  $$
* **Local Hour Angle ($H$) with East-positive longitude ($L_{\text{east}}$):**

  $$
  H = \theta_0 + L_{\text{east}} - \alpha
  $$
* **True Geometric Altitude ($h_0$, Eq. 13.6) and Compass Azimuth ($A_{\text{north}}$, Eq. 13.5):**

  $$
  \sin(h_0) = \sin(\phi)\sin(\delta) + \cos(\phi)\cos(\delta)\cos(H)
  $$

  $$
  \tan(A_{\text{south}}) = \frac{\sin(H)}{\cos(H)\sin(\phi) - \tan(\delta)\cos(\phi)}, \quad A_{\text{north}} = (A_{\text{south}} + 180^\circ) \pmod{360^\circ}
  $$

#### 5. Atmospheric Refraction — *Chapter 16 (Saemundsson's Formula, Eq. 16.4)*

$$
R_{\text{arcmin}} = \frac{1.02}{\tan\left(h_0 + \frac{10.3}{h_0 + 5.11}\right)}, \quad h_{\text{apparent}} = h_0 + \frac{R_{\text{arcmin}}}{60}
$$

Saemundsson's formula is not valid below about $-1^\circ$. Under that limit, refraction decays as $1/\tan(h_0)$ (the form NOAA uses below the horizon), matched at $-1^\circ$ so the apparent elevation stays continuous:

$$
R(h_0) = R(-1^\circ)\,\frac{\tan(1^\circ)}{\tan(-h_0)} \quad \text{for } h_0 < -1^\circ
$$

#### 6. Equation of Time ($E$) & Rising/Transit/Setting — *Chapter 28 (Eq. 28.3) & Chapter 15 (Eq. 15.1)*

* **Equation of Time ($E$):**
  With $y = \tan^2(\varepsilon / 2)$:

  $$
  E_{\text{rad}} = y\sin(2L_0) - 2e\sin(M) + 4ey\sin(M)\cos(2L_0) - \frac{1}{2}y^2\sin(4L_0) - \frac{5}{4}e^2\sin(2M)
  $$
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
* **Constellation:** the Sun's true longitude, less the general precession since J2000.0 (Chapter 21, Eq. 21.5), against the J2000.0 longitudes where the ecliptic crosses the IAU constellation boundaries. These were found with PyEphem and hold from 1900 to 2100; only the Libra–Scorpius one drifts noticeably (0.054° per century). The Sun changes constellation within 10 minutes of PyEphem's times.

---

<a name="documentation-française"></a>

## Documentation Française

**Helios** est une intégration personnalisée pour Home Assistant, sans aucune bibliothèque tierce, qui calcule la position du soleil et les heures solaires quotidiennes à partir d'équations astronomiques éprouvées (voir les [références des équations](#références-des-équations-pour-vérification)).

### Caractéristiques principales

* **Zéro dépendance externe :** Utilise exclusivement les modules standards `math` et `datetime` de Python (`"requirements": []` dans `manifest.json`).
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

Toutes les formules codées dans `custom_components/astraeos_helios/solar_engine.py` suivent l'ouvrage **Jean Meeus, *Astronomical Algorithms*, 2nd Edition (1998)** :

1. **Jour Julien ($JD$) et Siècle Julien ($T$) :** Chapitre 7 (Éq. 7.1, p. 61) et Chapitre 25 (Éq. 25.1, p. 163).
2. **Longitude moyenne ($L_0$), Anomalie moyenne ($M$) et Excentricité ($e$) :** Chapitre 25 (Éq. 25.2, 25.3 et 25.4, p. 163).
3. **Équation du centre ($C$), Distance ($R$) et Longitude apparente ($\lambda$) :** Chapitre 25 (Éq. 25.5 et 25.8, p. 164).
4. **Obliquité de l'écliptique ($\varepsilon_0, \varepsilon$) :** Chapitre 22 (Éq. 22.2, p. 147) et Chapitre 25 (Éq. 25.8, p. 165).
5. **Coordonnées équatoriales (Ascension droite $\alpha$ et Déclinaison $\delta$) :** Chapitre 25 (Éq. 25.6 et 25.7, p. 165).
6. **Temps sidéral à Greenwich ($\theta_0$) :** Chapitre 12 (Éq. 12.4, p. 88).
7. **Coordonnées horizontales locales (Azimut $A$ et Hauteur vraie $h_0$) :** Chapitre 13 (Éq. 13.5 et 13.6, p. 93). *Note : l'ouvrage mesure l'azimut à partir du Sud vers l'Ouest ; le moteur y ajoute $180^\circ \pmod{360^\circ}$ pour fournir l'azimut géographique standard (Nord = $0^\circ$, Est = $90^\circ$).*
8. **Réfraction atmosphérique ($R$) :** Chapitre 16 (Formule de Saemundsson, Éq. 16.4, p. 106). *Note : la formule n'est plus valable sous $-1^\circ$ environ ; en dessous, la réfraction décroît en $1/\tan(h_0)$ (forme utilisée par la NOAA sous l'horizon), raccordée à $-1^\circ$ pour que l'élévation apparente reste continue.*
9. **Équation du temps ($E$) :** Chapitre 28 (Éq. 28.3, p. 185).
10. **Lever, passage au méridien et coucher ($H_0$) :** Chapitre 15 (Éq. 15.1, p. 101-103) avec double itération pour affiner la déclinaison et l'équation du temps à l'instant exact de chaque événement. Chaque heure obtenue est ensuite corrigée avec la position du soleil à cet instant (p. 103), $\Delta m = -H/360^\circ$ pour un passage au méridien et $\Delta m = (h_0 - h_{\text{cible}})/(360^\circ\cos\delta\cos\phi\sin H)$ sinon, jusqu'à une correction inférieure à 10 ms : les capteurs binaires basculent aux heures affichées. Le soleil passe au méridien quand le temps solaire vrai vaut 12 h ($H = 0^\circ$) et au plus bas, au minuit solaire, quand il vaut 24 h ($H = 180^\circ$), soit $720 - 4L_{\text{est}} - E$ et $1440 - 4L_{\text{est}} - E$ minutes après 0 h UTC. Les seuils ($-0.8333^\circ$, $-6^\circ$, $-12^\circ$, $-18^\circ$, et $-4^\circ$ et $+6^\circ$ pour les heures bleue et dorée) portent sur la hauteur géométrique $h_0$ ; celui du lever et du coucher inclut déjà la réfraction et le demi-diamètre solaire, c'est donc aussi à lui que *Soleil au-dessus de l'horizon* compare $h_0$. Pour un observateur à l'altitude $h$ (en mètres), ce seuil est abaissé de la dépression de l'horizon visible, $1.76'\sqrt{h}$ (approximation des éphémérides nautiques, réfraction terrestre comprise ; le chapitre 15 suppose $h = 0$). Les crépuscules et les heures bleue et dorée, définis par rapport à l'horizon astronomique, ne changent pas.
11. **Durée du jour :** coucher moins lever. Les jours sans l'un des deux (autour du soleil de minuit), c'est le minuit solaire correspondant, pris à midi solaire $\pm$ 12 h, qui borne la durée.
12. **Constellation :** longitude vraie du soleil, moins la précession générale depuis J2000.0 (Chapitre 21, Éq. 21.5), comparée aux longitudes J2000.0 où l'écliptique croise les frontières des constellations de l'UAI. Ces longitudes ont été trouvées avec PyEphem et valent de 1900 à 2100 ; seule celle entre la Balance et le Scorpion dérive sensiblement (0,054° par siècle). Le soleil change de constellation à moins de 10 minutes des heures données par PyEphem.
