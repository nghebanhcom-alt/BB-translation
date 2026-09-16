"""Architecture.md §6.26.3/6.26.8 (S7 — dich FR->VI) — `detect_source_lang()`.

Doan van EN/FR ben duoi la van xuoi THAT (tu viet, khong phai cau ngan bia
san de bat trung tu khoa) dai ~500-700 tu MOI ngon ngu, chu de nganh banh —
dung tinh chat thuc te (nhieu cau, nhieu doan, tu vung da dang) thay vi cau
mau don gian de detector khong "hoc thuoc" 1-2 mau cau.
"""

from src.core.language_detector import detect_source_lang

_EN_TEXT = """
Bread has been at the heart of human civilization for thousands of years, and
the science behind a good loaf is more intricate than most home bakers ever
realize. When flour is mixed with water, the proteins glutenin and gliadin
begin to hydrate and link together, forming the elastic network we call
gluten. This network is what allows dough to stretch without tearing, and it
is also what traps the carbon dioxide produced by yeast during fermentation.
Without a well-developed gluten structure, a loaf would collapse under its
own weight before it ever reached the oven.

Yeast, whether wild or commercial, is a living organism that consumes sugars
in the dough and releases carbon dioxide and ethanol as by-products. This
process, known as fermentation, is what makes bread rise. The temperature of
the dough plays a critical role here: yeast activity roughly doubles for
every ten degrees Celsius increase, up to a point where the yeast itself
begins to die. A baker who understands this relationship can slow down or
speed up fermentation simply by adjusting the temperature of the room, the
water, or the dough itself.

Salt, though used in small quantities, performs several important functions
beyond simple seasoning. It tightens the gluten network, slows fermentation
just enough to allow for better flavor development, and helps control the
activity of enzymes that would otherwise break down starches too quickly.
Many professional bakers insist that a loaf without enough salt will taste
flat and will also have a weaker, more slack structure that is difficult to
shape.

The oven itself is where all of this preparation comes together. In the
first few minutes of baking, a phenomenon called oven spring occurs: the heat
causes the trapped gases to expand rapidly, the yeast experiences one last
burst of activity before dying from the heat, and the crust has not yet set
firm enough to prevent the loaf from growing. Steam injected into the oven
during this stage keeps the crust soft and pliable for longer, allowing for
maximum expansion before the surface hardens and browns.

Crust color and flavor come primarily from two chemical processes: the
Maillard reaction and caramelization. The Maillard reaction occurs between
amino acids and reducing sugars, producing hundreds of new flavor compounds
and the deep brown color we associate with a well-baked crust. Caramelization,
on the other hand, is the browning of sugars themselves under high heat, and
it contributes a different, more purely sweet character to the crust.

Understanding these principles does not require a laboratory, only careful
observation and a willingness to experiment. A baker who pays attention to
how dough feels at each stage, who notices how the crumb changes with small
adjustments to hydration or fermentation time, will eventually develop an
intuition that no recipe can fully teach. That intuition, built one loaf at a
time, is really what separates a competent baker from an exceptional one, and
it is why so many professionals still describe baking as both a science and
an art that rewards patience above almost everything else.
""".strip()

_FR_TEXT = """
Le pain occupe une place centrale dans de nombreuses cultures depuis des
siècles, et la science qui se cache derrière une belle miche est bien plus
subtile que ne le pensent la plupart des boulangers amateurs. Lorsque la
farine est mélangée à l'eau, les protéines appelées gluténine et gliadine
commencent à s'hydrater et à se lier entre elles, formant ce réseau élastique
que l'on nomme le gluten. Ce réseau permet à la pâte de s'étirer sans se
déchirer, et c'est également lui qui retient le gaz carbonique produit par la
levure pendant la fermentation. Sans un réseau de gluten bien développé, la
pâte s'effondrerait sous son propre poids avant même d'atteindre le four.

La levure, qu'elle soit sauvage ou commerciale, est un organisme vivant qui
consomme les sucres présents dans la pâte et qui rejette du gaz carbonique et
de l'éthanol comme sous-produits. Ce processus, que l'on appelle la
fermentation, est ce qui fait lever le pain. La température de la pâte joue
un rôle essentiel à cet égard : l'activité de la levure double approximativement
tous les dix degrés Celsius, jusqu'à un certain seuil au-delà duquel la levure
commence à mourir. Un boulanger qui comprend cette relation peut ralentir ou
accélérer la fermentation simplement en ajustant la température de la pièce,
de l'eau, ou de la pâte elle-même.

Le sel, bien qu'utilisé en petite quantité, remplit plusieurs fonctions
importantes qui vont bien au-delà du simple assaisonnement. Il resserre le
réseau de gluten, ralentit la fermentation juste assez pour permettre un
meilleur développement des arômes, et aide à contrôler l'activité des enzymes
qui, sinon, dégraderaient trop rapidement les amidons. Beaucoup de boulangers
professionnels insistent sur le fait qu'une miche sans assez de sel aura un
goût fade et une structure plus faible, plus difficile à façonner.

Le four lui-même est l'endroit où toute cette préparation se concrétise.
Pendant les premières minutes de cuisson, un phénomène appelé la poussée au
four se produit : la chaleur fait rapidement gonfler les gaz emprisonnés, la
levure connaît un dernier sursaut d'activité avant de mourir sous l'effet de
la chaleur, et la croûte n'est pas encore assez ferme pour empêcher la miche
de continuer à grossir. La vapeur injectée dans le four à ce moment-là garde
la croûte souple plus longtemps, ce qui permet une expansion maximale avant
que la surface ne durcisse et ne brunisse.

La couleur et la saveur de la croûte proviennent principalement de deux
réactions chimiques : la réaction de Maillard et la caramélisation. La
réaction de Maillard se produit entre les acides aminés et les sucres
réducteurs, produisant des centaines de nouveaux composés aromatiques ainsi
que la couleur brun foncé que l'on associe à une croûte bien cuite. La
caramélisation, quant à elle, correspond au brunissement des sucres eux-mêmes
sous l'effet d'une forte chaleur, et elle apporte à la croûte un caractère
différent, plus purement sucré.

Comprendre ces principes ne nécessite pas de laboratoire, seulement une
observation attentive et une volonté d'expérimenter. Un boulanger qui prête
attention à la façon dont la pâte se comporte à chaque étape, qui remarque
comment la mie change avec de petits ajustements d'hydratation ou de durée de
fermentation, finira par développer une intuition qu'aucune recette ne peut
vraiment enseigner. Cette intuition, construite miche après miche, est en
réalité ce qui distingue un boulanger compétent d'un boulanger exceptionnel,
et c'est pourquoi tant de professionnels décrivent encore la boulangerie
comme à la fois une science et un art qui récompense la patience avant
presque tout le reste.
""".strip()


def test_detects_real_english_passage() -> None:
    result = detect_source_lang(_EN_TEXT)
    assert result.lang == "en"
    assert result.token_count >= 500
    assert result.en_share > result.fr_share


def test_detects_real_french_passage() -> None:
    result = detect_source_lang(_FR_TEXT)
    assert result.lang == "fr"
    assert result.token_count >= 500
    assert result.fr_share > result.en_share


def test_english_and_french_shares_are_well_separated() -> None:
    """Architecture.md §6.26.3 bang nguong: ty so winner/loser >= 3.0. Doan
    van that o day tach biet manh hon nhieu — assert 1 bien do du rong de
    khong flaky, nhung du chat de bat regression neu wordlist bi pha vo."""
    en_result = detect_source_lang(_EN_TEXT)
    fr_result = detect_source_lang(_FR_TEXT)
    assert en_result.en_share / max(en_result.fr_share, 1e-9) >= 3.0
    assert fr_result.fr_share / max(fr_result.en_share, 1e-9) >= 3.0


def test_empty_text_returns_none_with_zero_counts() -> None:
    result = detect_source_lang("")
    assert result.lang is None
    assert result.token_count == 0
    assert result.en_share == 0.0
    assert result.fr_share == 0.0


def test_short_text_below_token_floor_returns_none() -> None:
    """Architecture.md §6.26.3: token_count < 500 -> khong ket luan, du ty le
    hu tu co the rat cao (chong ket luan tren bia/muc luc)."""
    short_en = "the quick brown fox jumps over the lazy dog " * 5
    result = detect_source_lang(short_en)
    assert result.token_count < 500
    assert result.lang is None


def test_gibberish_text_with_no_function_words_returns_none() -> None:
    """winner_share < 0.05 -> khong ket luan, khong doan bua."""
    gibberish = " ".join(["xqzwv"] * 600)
    result = detect_source_lang(gibberish)
    assert result.lang is None
    assert result.en_share == 0.0
    assert result.fr_share == 0.0
