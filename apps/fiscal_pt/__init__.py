"""apps/fiscal_pt — La conformite fiscale portugaise.

Trois obligations distinctes, trois modules, volontairement separes :

    assinatura.py   la signature RSA chainee (Despacho 8632/2014)
    atcud.py        le code unique de document (Portaria 195/2020)
    qr.py           le code QR imprime sur le document

Ils ne dependent ni de Django ni des modeles : ce sont des fonctions
pures, testables contre les exemples publies par l'AT. Les modeles, eux,
vivent dans models.py et se contentent d'appeler ces fonctions.

Cette separation n'est pas de l'elegance : c'est ce qui permet de
revalider le calcul contre un texte officiel sans monter une base de
donnees, et donc de le faire souvent.
"""
