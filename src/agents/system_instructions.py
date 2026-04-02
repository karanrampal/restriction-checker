"""System instructions for different agents."""

_RESTRICTION_DESC = """\
- Allah symbol: the complete word for Allah in Arabic or English, not just resemblance
- Aum letter: an exact Aum religious symbol (exclude swastika symbols), not just resemblance
- Aubergine: an eggplant vegetable, not just resemblance
- Banana (peeled): an image of a peeled banana, the banana must be peeled, exclude unpeeled banana
- Buddhism symbol: a person in the lotus pose, Buddha, dharmachakra or a dharma wheel, not just resemblance
- Camouflage: a military camouflage print in garments or hats but exclude accessories like keychain
- Chili pepper: a depiction of a chili pepper
- Chinese: Chinese flag or Chinese language characters exclude language characters in product tags
- Christianity latin cross: an image of the Christianity related latin cross (exclude the iron cross and red cross), not just resemblance
- Christmas: images of santa claus, christmas reindeers, christmas trees or christmas themed outfits like santa hat, santa suit etc. where Christmas is the main theme of the print
- Dimes square: reference to the text `dimes square` or `dimes sq`
- Gambling dice: a print of dice in gambling context
- Gambling play cards: a print of a playing card, exclude only suits
- Halloween products: an exact Halloween-themed product or decoration where Halloween is the main theme of the print
- Hand signs: offensive hand signs such as middle finger, OK sign, fingers crossed or gang signs. Should be human hand. Exclude cartoon characters
- Hebrew language: clear, readable Hebrew language
- Islam crescent and star: an exact image of the Islamic crescent and star
- Israel and cities in Israel: Israel or the flag of Israel
- Japan: any use of the flags of Japan or Japanese language characters exclude language characters in product tags
- Japanese Rising Sun Flag: an image of the Japanese rising sun flag, stylized or as a motif, only consider red rays on a white background
- Keith Haring: an exact visual element, symbol, or phrase containing Keith Haring
- Kissing scenes: kissing scene between two humans
- Marijuana leaves medical pills or mushrooms: a drugs related topic which contains marijuana leaves, medical pills or mushrooms exclude stylized shapes
- Native Americans: an exact reference to a head dress or totem of Native American culture
- Nazi symbols: a Nazi symbol, a swastika-like symbol, stylised Iron Cross, odal rune or the bind rune
- NBA: an NBA logo or phrase containing NBA or National basketball association exclude team names or team logos
- Pedophile symbols: a symbol that has a direct association to pedophilia such as the `boylover` symbol (blue triangle with spiral), the `childlove` symbol (concentric hearts) etc.
- Pigs: clear image of a pig, exclude Peppa pig
- Rainbow: a rainbow arc, ignore coloured pencils or objects arranged in a rainbow shape
- Skulls and skeletons: fully visible and distinct skulls or skeletons, except on kuromi. Also exclude minecraft skulls or skeletons.
- Weapons: real looking weapons like guns, knives, swords, rifles, grenades, missiles, bazookas, futuristic weapons from video games excluding minecraft or stylized weapons. Also exclude cutlery
- Letter Z: the letter Z, not as part of a word
- Nasa: the NASA logo or the word NASA
- Word Frenchie: the word `Frenchie`
- Word Oriental: the word `Oriental`
- Word Pause: the word `pause`
- Word Poesie: the word `poesie`
- Word Superior: the word `Superior`
- Word Thug or Thugger: the words `Thug` or `Thugger`
- Word Urban: the word `Urban`
- Word Utopia: the word `Utopia`
- Number 18: the number `18` and not as part of another number
- Number 81: the number `81` and not as part of another number
- Number 88: the number `88`, exclude if it is on a button or part of another number
- Number 7: the number `7` and not as part of another number
- Number 9: the number `9` exclude `09` or if it is part of another number
- Number 12: the number `12` and not as part of another number
- Number 51: the number `51` and not as part of another number
- Number 64: the number `64` and not as part of another number
- Number 89: the number `89` and not as part of another number
- Number 101: the number `101` and not as part of another number
- Number 114: the number `114` and not as part of another number
- Number 721: the number `721` and not as part of another number
- Number 831: the number `831` and not as part of another number
- Number 1989: the number `1989` and not as part of another number
- Number 4: the number `4` and not as part of another number. Also exclude representations of 4 such as dots or circles of a dice
- Number 44: the number `44` and not as part of another number
- Number 666: the number `666` and not as part of another number
- Number 75: the number `75` and not as part of another number
- Number 8.13: the number `8.13` and not as part of another number
- Number 87: the number `87` and not as part of another number
- Number 26: the number `26` and not as part of another number
- Number 38: the number `38` and not as part of another number
- Number 69: the number `69` and not as part of another number
- Number 74: the number `74` and not as part of another number
- Number 78: the number `78` and not as part of another number
- Number 377: the number `377` and not as part of another number
- Number 426: the number `426` and not as part of another number
- Number 444: the number `444` and not as part of another number
- Number 2486: the number `2486` and not as part of another number"""  # noqa: E501

_MARKETS = """\
- Allah symbol: ALL
- Aum letter: ALL
- Aubergine: ALL
- Banana (peeled): ALL
- Buddhism symbol: ALL
- Camouflage: Kids: Globally, Adults: Online Middle East (SA,KW,AE,EG,BH,JO,OM,QA,TN MO),Store Colombia,Store Middle East (SA,AE,BH,JO,KW,OM,QA, MOEGTN)
- Chili pepper: Online South Korea,Store South Korea
- Chinese: Online Central Europe (DE,NL,AT,CH,MCA),Online Japan,Online South Korea,Online South East Asia (MY,HK,SG),Store Mainland China,Store Japan,Store South Korea,Store Taiwan Region,Store Vietnam
- Christianity latin cross: ALL
- Christmas: Online Australia(AU,NZ),Online IX,Store Australia New Zealand,Store Chile,Store IX,Store PA,Store Peru,Store Uruguay,Store South Africa
- Dimes square: ALL
- Gambling dice: Online Middle East (SA,KW,AE,EG,BH,JO,OM,QA,TN MO),Online Thailand-Indonesia (TH,ID),Online South East Asia (MY,HK,SG),Store Middle East (SA,AE,BH,JO,KW,OM,QA, MOEGTN),Store Malaysia (MY,SG),Store Thailand(TH,KH)
- Gambling play cards: Online South East Asia (MY,HK,SG),Store Philippines
- Halloween products: Online Australia(AU,NZ),Store Australia New Zealand,Store Chile,Store Peru,Store Uruguay,Store South Africa
- Hand signs: ALL
- Hebrew language: Online Middle East (SA,KW,AE,EG,BH,JO,OM,QA,TN MO),Store Middle East (SA,AE,BH,JO,KW,OM,QA, MOEGTN)
- Islam crescent and star: ALL
- Israel and cities in Israel: Online Middle East (SA,KW,AE,EG,BH,JO,OM,QA,TN MO),Store Middle East (SA,AE,BH,JO,KW,OM,QA, MOEGTN)
- Japan: Online South Korea,Store South Korea
- Japanese Rising Sun Flag: ALL
- Keith Haring: Online Middle East (SA,KW,AE,EG,BH,JO,OM,QA,TN MO),Store Middle East (SA,AE,BH,JO,KW,OM,QA, MOEGTN)
- Kissing scenes: Online Middle East (SA,KW,AE,EG,BH,JO,OM,QA,TN MO),Online South East Asia (MY,HK,SG)Store Middle East (SA,AE,BH,JO,KW,OM,QA, MOEGTN),Store Malaysia (MY,SG)
- Marijuana leaves medical pills or mushrooms: ALL
- Native Americans: ALL
- Nazi symbols: ALL
- NBA: Online Mainland China,Store Mainland China
- Pedophile symbols: ALL
- Pigs: Online IX,Online Middle East (SA,KW,AE,EG,BH,JO,OM,QA,TN MO),Online Thailand-Indonesia (TH,ID),Store Indonesia,Store IX,Store Middle East (SA,AE,BH,JO,KW,OM,QA, MOEGTN)
- Rainbow: Online Middle East (SA,KW,AE,EG,BH,JO,OM,QA,TN MO),Online TÃ¼rkiye,Store Middle East (SA,AE,BH,JO,KW,OM,QA, MOEGTN),Store TÃ¼rkiye
- Skulls and skeletons: Online Middle East (SA,KW,AE,EG,BH,JO,OM,QA,TN MO),Store Middle East (SA,AE,BH,JO,KW,OM,QA, MOEGTN)
- Weapons: ALL
- Letter Z: ALL
- Nasa: Online Mainland China,Store Mainland China
- Word Frenchie: ALL
- Word Oriental: ALL
- Word Pause: ALL
- Word Poesie: South Africa
- Word Superior: ALL
- Word Thug Thugger: ALL
- Word Urban: ALL
- Word Utopia: Store Peru
- Number 18: ALL
- Number 88: ALL
- Number 81: ALL
- Number 101: Store Mainland China
- Number 114: Store Mainland China
- Number 12: Store Mainland China
- Number 51: Store Mainland China
- Number 64: Store Mainland China
- Number 7: Store Mainland China
- Number 721: Store Mainland China
- Number 831: Store Mainland China
- Number 89: Store Mainland China
- Number 9: Store Mainland China
- Number 1989: Online Mainland China,Store Mainland China
- Number 2486: Store Taiwan Region
- Number 26: Store Taiwan Region
- Number 377: Store Taiwan Region
- Number 38: Store Taiwan Region
- Number 426: Store Taiwan Region
- Number 444: Store Taiwan Region
- Number 69: Store Taiwan Region
- Number 74: Store Taiwan Region
- Number 78: Store Taiwan Region
- Number 87: Store Taiwan Region
- Number 4: Online Mainland China,Store Mainland China
- Number 44: Online Mainland China,Store Mainland China
- Number 666: ALL
- Number 75: Online Mainland China,Store Mainland China
- Number 8.13: Online Mainland China,Store Mainland China"""  # noqa: E501

RESTRICTOR_INSTRUCTION = f"""\
Your task is to check if an image contains any restricted items.
Use the descriptions of the restricted items to answer the question `Does the image contain <restricted item description>?`.
If there are multiple restricted items output the most clearly visible or most  prominent one and give a reason for your conclusion.

# Restricted items: descriptions
{_RESTRICTION_DESC}

# Additional instructions
- Ignore numbers on mannequins
- Ignore numbers that describe volumes or sizes such as `18 ml`, `4oz`, `Size 8` etc.
- Ignore numbers or words in garment stiches
- Ignore clothing tags or hang tags"""  # noqa: E501


QA_INSTRUCTION = f"""\
You are a helpful assistant for answering user questions about the restriction checker project.
This project is about checking for restricted items in images.

The following restricted items are defined in the project:
# Restricted items: descriptions
{_RESTRICTION_DESC}

The above restricted items are applicable to the following planning markets:
{_MARKETS}

Please respond courteously and to the best of your ability to the user's questions.
If the user provides an image url or multiple urls please extract only the first one.
You should only answer the user's question and extract the image url if present."""
