from os import path


gitBooksToDelete = """
https://gist.github.com/distbit0/a0263595eacd88182b50c8061f06a0a5
https://gist.github.com/distbit0/ee7fac24eeb6bf27d4003dec9970728e
https://gist.github.com/distbit0/ffc4af8d0c2cedda7e6b724fb8a6be6b
https://gist.github.com/distbit0/7af0d39e07428a8e71177ac668dc9bd2
https://gist.github.com/distbit0/5b462abbb3000e130ffab5a9247732ee
https://gist.github.com/distbit0/1e7ebc7b3b143fc187c400859300dd4a
https://gist.github.com/distbit0/ed170df01cbd2d66413fc9b24a440494
https://gist.github.com/distbit0/db8ca215807476b0834946d2ee8c8311
https://gist.github.com/distbit0/10f901784f3e415a7da1a8c73e01b831
https://gist.github.com/distbit0/5cc3032545782c84622a187b48246e03
https://gist.github.com/distbit0/20586b978612bdef15387999ecae5e3d
https://gist.github.com/distbit0/6b139a25740cc61907937446c4b18034
https://gist.github.com/distbit0/58002b11220c2aea20de5566c7aba6ad
https://gist.github.com/distbit0/d3bd0fd185cad8b385e3149732e076db
https://gist.github.com/distbit0/b21b39e056567cf658005fbe9fbb75d8
https://gist.github.com/distbit0/8a4c71e3a91a863d6d0db4e215968672
https://gist.github.com/distbit0/64af20013e76e3629db63ec5cc76682f
https://gist.github.com/distbit0/9cd513435d2deb406a3a56726d73db07
https://gist.github.com/distbit0/fe77f92f247082f95539a136a3215748
https://gist.github.com/distbit0/318ed381cef7f1995b6a20ced89f8376
https://gist.github.com/distbit0/b3e62b17b276324fdae8730db47a582f
https://gist.github.com/distbit0/cfb16f7ddfc6203a3f1ebbeba5b789ae
https://gist.github.com/distbit0/e3bc0b3e9308b2db8cf23cae70b350de
https://gist.github.com/distbit0/e5a3698106ce2aa1713592a907be0749
https://gist.github.com/distbit0/963aa8e18dca6ca1714d82f1709c58a1
https://gist.github.com/distbit0/266688691b7fc6099d6dd0b872d7dd03
https://gist.github.com/distbit0/7efd36314736ca71dd73ed41dccfd516
https://gist.github.com/distbit0/160fe7fb3b43972f110f48494360e05c
https://gist.github.com/distbit0/f0cb83e7996c8b60bea056d1196e83d6
https://gist.github.com/distbit0/68af68d876ef19ee1a36be2013f80a4d
https://gist.github.com/distbit0/0695c1f65614374d461fb6de6a5691ce
https://gist.github.com/distbit0/04a3877d6e2cd8919b444cbfb46983e5
https://gist.github.com/distbit0/c54329b1b8684a8fe959b4e858ad277c
https://gist.github.com/distbit0/b5cc375039b4c66c2b92a4df086ca537
https://gist.github.com/distbit0/dbc6e13a7936e30e5943761482d4704e
https://gist.github.com/distbit0/3f7f149e3d705d3aa78ea8445236d5c2
https://gist.github.com/distbit0/203830a9d6015f948144f6f4fa3d4686
https://gist.github.com/distbit0/9d5147211290e0e7d28f37d66a9130f7
https://gist.github.com/distbit0/d301fe44d54ff1381be61816716bb2a7
https://gist.github.com/distbit0/a7139942d49544e3b1a2bf291453e913
https://gist.github.com/distbit0/3f12bf8f3b27a37ac86c0aedb170f8d8
https://gist.github.com/distbit0/9a0f14c19532ad6d6fe600f358d75538
https://gist.github.com/distbit0/43454ca4a9292bb1a3a56e04b0f57fa7
https://gist.github.com/distbit0/d8a7f08f19c1cfd17d6987096f90f872
https://gist.github.com/distbit0/434079530d2a9b5800298b0869c460da
https://gist.github.com/distbit0/1adb4b53b4dceb499467725af746784e
https://gist.github.com/distbit0/ccf35582d8e1c5b36a06511a9dcb889c
https://gist.github.com/distbit0/75428df8a8899c45f5393c62968894d8
https://gist.github.com/distbit0/d48120eda1cbd92242cbc6b547f56cba
https://gist.github.com/distbit0/839ce4607f60f835732f3928bcf9cf56
https://gist.github.com/distbit0/d24c9df96f65ba0e301fcc712018fcb4
https://gist.github.com/distbit0/7269c0f552bfbad58851222f3de14730
https://gist.github.com/distbit0/02c38e724b9053f1fae6cd215fe93987
https://gist.github.com/distbit0/e56281ae69f3064a04e3755b8fc4e2f3
https://gist.github.com/distbit0/ab43714d11c856e226b8ca4e361e3879
https://gist.github.com/distbit0/dc06a2681a1c4e4089bba567e04a97fc
https://gist.github.com/distbit0/0f7845c8c9300bf0552382b3eff9938e
https://gist.github.com/distbit0/8f452a08e7f078f8ae568d5387221e8e
https://gist.github.com/distbit0/3e6dc7d3b1dfe3d3629815e870225efb
https://gist.github.com/distbit0/f454a639e2bb8b079117d63d98012b94
"""

gitBooksToDelete = [
    book.split("/")[-1] for book in gitBooksToDelete.strip().split("\n")
]


print("gitBooksToDelete: ", gitBooksToDelete)


gitBooksToAdd = """
https://gist.github.com/741b5a5910c63d95136b5094730d148f /home/pimania/ebooks/GITB__Lending___Baseline · GitHub.html 
https://gist.github.com/c8d2b64e594bc8ec1b4692da58597ba0 /home/pimania/ebooks/GITB__Concepts___Baseline · GitHub.html 
https://gist.github.com/c1f0c6d65edb92c5ad4b9074745a64be /home/pimania/ebooks/GITB__Faq___Baseline · GitHub.html 
https://gist.github.com/45327b229b5f111b0408e653c8ded91f /home/pimania/ebooks/GITB__Deposit_Liquidity___Chromatic_Protocol · GitHub.html 
https://gist.github.com/13a0b5a9e0583685d59dfd50416aa6cc /home/pimania/ebooks/GITB__Market_Making___Baseline · GitHub.html 
https://gist.github.com/64b10ba04dd118bf6256a73c39f3fa72 /home/pimania/ebooks/GITB__Take_profit_and_stop_loss_orders__TP_SL____Hyperliquid_Docs.html 
https://gist.github.com/0b40a5d8863e4295e43fb6ce59b1cf4f /home/pimania/ebooks/GITB__Keys_and_Stealth_Addresses___Nocturne · GitHub.html 
https://gist.github.com/6a69e9202f200abaa09263de66ac4cf8 /home/pimania/ebooks/GITB__Pendle_Strategies___The_Wise_Ecosystem · GitHub.html 
https://gist.github.com/60e5dfc8a4d88509378cf875d5902fff /home/pimania/ebooks/GITB__Depleted_Asset_Protection___Ammalgam_Protocol.html 
https://gist.github.com/f459b00d2da45d2ad61ec46c358b799d /home/pimania/ebooks/GITB__Introduction___Quiver · GitHub.html 
https://gist.github.com/198143b513e3475ef5d875805c3f9d37 /home/pimania/ebooks/GITB__Architecture_Overview___Ammalgam_Protocol ·.html 
https://gist.github.com/50960ab0a5af3e8f9c50b3ddc37ac8b7 /home/pimania/ebooks/GITB__Funding___Hyperliquid_Docs · GitHub.html 
https://gist.github.com/4576128ba544b219dd23a59ffd1bf64b /home/pimania/ebooks/GITB__Deposits___Nocturne · GitHub.html 
https://gist.github.com/b7061da4895031d584534e282f9e4074 /home/pimania/ebooks/GITB__Notes__Commitment_Tree__Nullifiers__and_JoinSplits___Nocturne.html 
https://gist.github.com/e0a53186742276643b785a8dbbf50af5 /home/pimania/ebooks/GITB__Index_perpetual_contracts___Hyperliquid_Docs.html 
https://gist.github.com/18685d71fb3df0db80fac9f67ed1d788 /home/pimania/ebooks/GITB__Margining___Hyperliquid_Docs · GitHub.html 
https://gist.github.com/3131d9f091e24540cb72c36de49b224f /home/pimania/ebooks/GITB__Gensyn_Litepaper___Gensyn · GitHub.html 
https://gist.github.com/fb75e0e21bcc2fe5d71a82827d4ea50b /home/pimania/ebooks/GITB__Quiver_Engine___Quiver · GitHub.html 
https://gist.github.com/9e1d9cb705fd5e22d96b6de28709e7ea /home/pimania/ebooks/GITB__Power_Farms___The_Wise_Ecosystem · GitHub.html 
https://gist.github.com/4e82c8bc6bdee3ea5985dbb308dfd68b /home/pimania/ebooks/GITB__Overview___Ammalgam_Protocol · GitHub.html 
https://gist.github.com/53c099c5a334c7131ff7a4612fb4972e /home/pimania/ebooks/GITB__Centralized_Crypto_Exchanges___Quiver · GitHub.html 
https://gist.github.com/99b933ad630cfb5b16d91b09bd4b772d /home/pimania/ebooks/GITB__Introduction___Quiver · GitHub 1.html 
https://gist.github.com/5e2e9b7f566d7d859c2c8609238ace58 /home/pimania/ebooks/GITB__LASA_AI___The_Wise_Ecosystem · GitHub.html 
https://gist.github.com/73838bff450e2af2bd8e086f525e7f9e /home/pimania/ebooks/GITB__Operations___Nocturne · GitHub.html 
https://gist.github.com/f5abee709bc22545a378de0f11b3846a /home/pimania/ebooks/GITB__DeFi_Exchanges___Quiver · GitHub.html 
https://gist.github.com/cc08a35254c719043e3d8ab28fc3d490 /home/pimania/ebooks/GITB__Order_types___Hyperliquid_Docs · GitHub.html 
https://gist.github.com/37343f177fb523caa3b030a19637eccc /home/pimania/ebooks/GITB__Quiver_Sweeper__Aggregator____Quiver · GitHub.html 
https://gist.github.com/4ae078534658175016283e0c382e6a45 /home/pimania/ebooks/GITB__Liquidations___Hyperliquid_Docs · GitHub.html 
https://gist.github.com/9891863c5407d575cf7ae4b846889617 /home/pimania/ebooks/GITB__Liquidity_and_Arbitrage___Quiver · GitHub.html 
https://gist.github.com/916131f06fdee164cf8476bf0d586fa2 /home/pimania/ebooks/GITB__Protocol_Overview___Nocturne · GitHub.html 
https://gist.github.com/772927bd609ddb88ca6bd45d2d638291 /home/pimania/ebooks/GITB__Traditional_Exchanges___Quiver · GitHub.html 
https://gist.github.com/e3538d9244fe751c8c251d4b336d3339 /home/pimania/ebooks/GITB__Stealth_Addresses___Nocturne · GitHub.html 
https://gist.github.com/368106448f5ed21ed5d414356f039cd9 /home/pimania/ebooks/Reputation arbitration and identity/Arbitration/How it works - Unicrow Documentation.html 
https://gist.github.com/0553fdd5144a6c807e0fa4a8f10941dd /home/pimania/ebooks/Cryptocurrency/rollups and lightning/Account abstraction support - zkSync — Accelerating.html 
https://gist.github.com/a0263595eacd88182b50c8061f06a0a5 /home/pimania/ebooks/Cryptocurrency/rollups and lightning/L1  L2 Interoperability - zkSync — Accelerating the.html 
https://gist.github.com/4fb7d5697d629b43b188e2a211d02635 /home/pimania/ebooks/Cryptocurrency/rollups and lightning/Bridging assets - zkSync — Accelerating the mass.html 
https://gist.github.com/b64b237188773e4c0844713053cb68e1 /home/pimania/ebooks/Cryptocurrency/rollups and lightning/System contracts - zkSync — Accelerating the mass.html 
https://gist.github.com/9d7b788866e3bc11116895215f23a3da /home/pimania/ebooks/Cryptocurrency/rollups and lightning/Layer 2 Guide - saddle.finance.html 
https://gist.github.com/16fb909ca7314f16be26918f6257caac /home/pimania/ebooks/Cryptocurrency/rollups and lightning/Fuel - Docs - Fuel Overview.html 
https://gist.github.com/ee7fac24eeb6bf27d4003dec9970728e /home/pimania/ebooks/Cryptocurrency/rollups and lightning/UTXO - zkopru.html 
https://gist.github.com/23ccb7f68903ce8bd30c11f70b166a22 /home/pimania/ebooks/Cryptocurrency/rollups and lightning/Fee mechanism - zkSync — Accelerating the mass adoption.html 
https://gist.github.com/ffc4af8d0c2cedda7e6b724fb8a6be6b /home/pimania/ebooks/Cryptocurrency/rollups and lightning/Block structure & serialization - zkopru.html 
https://gist.github.com/7af0d39e07428a8e71177ac668dc9bd2 /home/pimania/ebooks/Cryptocurrency/rollups and lightning/Vovo PPP on Arbitrum - Vovo Finance.html 
https://gist.github.com/6c3369fa73ef2216aad6d28c77a8c7d8 /home/pimania/ebooks/Cryptocurrency/rollups and lightning/Account - zkopru.html 
https://gist.github.com/4fa68a3d9db450671e255e3503733cf6 /home/pimania/ebooks/Cryptocurrency/rollups and lightning/Transaction - zkopru.html 
https://gist.github.com/f934a340591fc0c250ff96ab23c8c30f /home/pimania/ebooks/Cryptocurrency/rollups and lightning/Blocks - zkSync — Accelerating the mass adoption.html 
https://gist.github.com/04b17896cbc9c66ccf0c6bb912d0be79 /home/pimania/ebooks/Cryptocurrency/rollups and lightning/Merkle trees - zkopru.html 
https://gist.github.com/5b462abbb3000e130ffab5a9247732ee /home/pimania/ebooks/Cryptocurrency/rollups and lightning/L1 - L2 communication - zkSync — Accelerating the.html 
https://gist.github.com/3db744ba9080d9cf2ab404fa14aae002 /home/pimania/ebooks/Cryptocurrency/rollups and lightning/Token support - zkopru.html 
https://gist.github.com/ed8c0f6e7212cbe0d38299065bbee4a8 /home/pimania/ebooks/Cryptocurrency/rollups and lightning/Fuel - Docs - Security Analysis.html 
https://gist.github.com/74bd4bd46607add0d1a0df11f540f3e5 /home/pimania/ebooks/Cryptocurrency/rollups and lightning/Transactions - zkSync — Accelerating the mass adoption.html 
https://gist.github.com/0c04601da33cd971a2c6b1d483fd8a48 /home/pimania/ebooks/Cryptocurrency/rollups and lightning/zkSync basics - zkSync — Accelerating the mass adoption.html 
https://gist.github.com/1f3ed20fba35bac5cfde78b6c33a3bd7 /home/pimania/ebooks/Cryptocurrency/rollups and lightning/L2 - L1 communication - zkSync — Accelerating the.html 
https://gist.github.com/2336eb3b18e4e039418a69d512281fa6 /home/pimania/ebooks/Cryptocurrency/rollups and lightning/API Reference.html 
https://gist.github.com/47f21e77215e1df04ae964cc72d0b4ce /home/pimania/ebooks/Cryptocurrency/rollups and lightning/Merged leaves & optimistic rollup - zkopru.html 
https://gist.github.com/a200c00491c51666401ac828e39e817a /home/pimania/ebooks/Computer Science/software dev/Explaining Atomics in Rust - Explaining Atomics in.html 
https://gist.github.com/bca17ec7c1296740f0b220e6dccd8d45 /home/pimania/ebooks/Computer Science/networks/Lot49 - Lot49.html 
https://gist.github.com/5cf3f7ac3eee6f778b0c3642c42c647c /home/pimania/ebooks/distributed protocols/general/Introduction.html 
https://gist.github.com/5c2bdf6bcb94499e75085092d1f37f34 /home/pimania/ebooks/Decentralised Finance/options/FAQ - Liqui.html 
https://gist.github.com/be24ae6744a4c6465e4bb22e68406e26 /home/pimania/ebooks/Decentralised Finance/options/Replicating Market Makers - Duality Documentation.html 
https://gist.github.com/da883a012e261f4c19447568dfda6e59 /home/pimania/ebooks/Decentralised Finance/options/Introduction - Opyn V2.html 
https://gist.github.com/1e7ebc7b3b143fc187c400859300dd4a /home/pimania/ebooks/Decentralised Finance/options/Overview - Serum.html 
https://gist.github.com/ff173e704620b8b5f20e735cc6485185 /home/pimania/ebooks/Decentralised Finance/options/How It Works - Welcome to Lift.html 
https://gist.github.com/4fad222a9362c5c94ed2cd1f17c3c873 /home/pimania/ebooks/Decentralised Finance/options/Mechanics - Y2K Finance.html 
https://gist.github.com/ed170df01cbd2d66413fc9b24a440494 /home/pimania/ebooks/Decentralised Finance/options/Use Cases - Opyn V2.html 
https://gist.github.com/66e5aea6412768ddaecb3d43dc0eaee1 /home/pimania/ebooks/Decentralised Finance/options/Determining Strike Prices - Y2K Finance.html 
https://gist.github.com/db8ca215807476b0834946d2ee8c8311 /home/pimania/ebooks/Decentralised Finance/cross chain and bridges/Comparing Mechanisms - Nomad Docs.html 
https://gist.github.com/c50e4a8157f3edc99a8358ca79be426f /home/pimania/ebooks/Decentralised Finance/cross chain and bridges/Overview - Nomad Docs.html 
https://gist.github.com/d85523a32c5da27e3d6c137e7f090902 /home/pimania/ebooks/Decentralised Finance/cross chain and bridges/Optics - Celo Docs.html 
https://gist.github.com/1f891c2c7af64e22f614fa05d6799b59 /home/pimania/ebooks/Decentralised Finance/cross chain and bridges/Technology - THORChain Docs.html 
https://gist.github.com/28f8a3f2e75f86f557e264b23b685806 /home/pimania/ebooks/Decentralised Finance/cross chain and bridges/Optimistic Verification - Nomad Docs.html 
https://gist.github.com/dbde8cd361c346ace4a073548918ebdf /home/pimania/ebooks/Decentralised Finance/cross chain and bridges/Native Verification - Nomad Docs.html 
https://gist.github.com/29827d065635728c0528394e44e1dfdf /home/pimania/ebooks/Decentralised Finance/cross chain and bridges/Introduction - Nomad Docs.html 
https://gist.github.com/b17b24cd91fdcb90cb1db54c7e920641 /home/pimania/ebooks/Decentralised Finance/cross chain and bridges/Cross-chain Messaging - Nomad Docs.html 
https://gist.github.com/e383a1364c440175c2559d33938ae167 /home/pimania/ebooks/Decentralised Finance/cross chain and bridges/How to Bridge - Nomad Docs.html 
https://gist.github.com/1af1adbbc5332921fe1ea8b56e4420e7 /home/pimania/ebooks/Decentralised Finance/yield farming and vaults/Limit Order Tranches - Duality Documentation.html 
https://gist.github.com/9c02c5d42f2771131577dfddbb90b0f2 /home/pimania/ebooks/Decentralised Finance/yield farming and vaults/Use Cases - Sense.html 
https://gist.github.com/c45ae14f90e9eb46de75b6605c91dcd3 /home/pimania/ebooks/Decentralised Finance/yield farming and vaults/Overview - Vovo Finance.html 
https://gist.github.com/10f901784f3e415a7da1a8c73e01b831 /home/pimania/ebooks/Decentralised Finance/yield farming and vaults/Providing Liquidity - Timeless Docs.html 
https://gist.github.com/4c149d065e61ab5f63ab754f96e64171 /home/pimania/ebooks/Decentralised Finance/yield farming and vaults/Investment Strategies - Vovo Finance.html 
https://gist.github.com/518cac18e1863647cb7d1d0102fa68f9 /home/pimania/ebooks/Decentralised Finance/insurance/Insurance - Developer Docs.html 
https://gist.github.com/0eb4911af223143c116a8fe2b2d80733 /home/pimania/ebooks/Decentralised Finance/insurance/Governance - InsurAce Protocol.html 
https://gist.github.com/5aeb62287d3e966f313ebfcf936e5eef /home/pimania/ebooks/Decentralised Finance/insurance/Investment - InsurAce Protocol.html 
https://gist.github.com/e4d9d66615f3a3181827f697ec5ee558 /home/pimania/ebooks/Decentralised Finance/insurance/Wildfire - Y2K Finance.html 
https://gist.github.com/f309dc582f514a81f82dd476389b9357 /home/pimania/ebooks/Decentralised Finance/insurance/Risk Assessment - InsurAce Protocol.html 
https://gist.github.com/655ebc429992b0c24a7ae742854e932c /home/pimania/ebooks/Decentralised Finance/insurance/Capital Management - InsurAce Protocol.html 
https://gist.github.com/4b24031e502b27ce31f70c917e8d0409 /home/pimania/ebooks/Decentralised Finance/insurance/Insurance Fund - UXD Protocol.html 
https://gist.github.com/5cc3032545782c84622a187b48246e03 /home/pimania/ebooks/Decentralised Finance/insurance/FAQ - Cozy Documentation.html 
https://gist.github.com/20586b978612bdef15387999ecae5e3d /home/pimania/ebooks/Decentralised Finance/insurance/Y2K - Y2K Finance.html 
https://gist.github.com/6b139a25740cc61907937446c4b18034 /home/pimania/ebooks/Decentralised Finance/insurance/Case study - Cozy Documentation.html 
https://gist.github.com/58002b11220c2aea20de5566c7aba6ad /home/pimania/ebooks/Decentralised Finance/insurance/Overview - Cozy Documentation.html 
https://gist.github.com/d58dd542d51b48ea6de5e4e481833890 /home/pimania/ebooks/Decentralised Finance/insurance/Pricing Models - InsurAce Protocol.html 
https://gist.github.com/d3bd0fd185cad8b385e3149732e076db /home/pimania/ebooks/Decentralised Finance/insurance/Claim Assessment - InsurAce Protocol.html 
https://gist.github.com/dd16759052a46e8530e3fccd23edb030 /home/pimania/ebooks/Decentralised Finance/dexes/Single-Sided Incentives - Maverick Docs.html 
https://gist.github.com/4b3fded6ae178b6bc4329256b706f9ce /home/pimania/ebooks/Decentralised Finance/dexes/Rebalance - Liqui.html 
https://gist.github.com/af66cc84d7cf057247d010a4bec00bac /home/pimania/ebooks/Decentralised Finance/dexes/Shared Liquidity - Duality Documentation.html 
https://gist.github.com/61c8552f4110e2167fb81852cf0f206f /home/pimania/ebooks/Decentralised Finance/dexes/Smart Liquidity Pool (SLP) - ApeX Pro.html 
https://gist.github.com/4b98f74b91c6d956d7800b931cf04628 /home/pimania/ebooks/Decentralised Finance/dexes/AMMs and Orderbooks - Duality Documentation.html 
https://gist.github.com/66bb00899fb26452dc8815674a135c41 /home/pimania/ebooks/Decentralised Finance/dexes/Liquidity Pools - Duality Documentation.html 
https://gist.github.com/68b5e77d96a0f7f5e50bf5951a9d2455 /home/pimania/ebooks/Decentralised Finance/dexes/Swaps - Duality Documentation.html 
https://gist.github.com/dff7f0605b2c1a42bc2253358744ec5f /home/pimania/ebooks/Decentralised Finance/dexes/What is Duality - Duality Documentation.html 
https://gist.github.com/fc562f72347a5508d6c4246027abcebf /home/pimania/ebooks/Decentralised Finance/dexes/Math - Liqui.html 
https://gist.github.com/f2bc80898c3c16d1d8d95a0a3e82e778 /home/pimania/ebooks/Decentralised Finance/dexes/Understanding Modes - Maverick Docs.html 
https://gist.github.com/3ca388fface1503a31f64cfe8fe034a9 /home/pimania/ebooks/Decentralised Finance/dexes/Features - V1 TWAMM.html 
https://gist.github.com/0ada6c0fb8fcffb41d059ca4ae9ecc3d /home/pimania/ebooks/Decentralised Finance/dexes/Overview - Liqui.html 
https://gist.github.com/2cd7f44d50628ede530974192fd87125 /home/pimania/ebooks/Decentralised Finance/dexes/Understanding Boosted Positions - Maverick Docs.html 
https://gist.github.com/3d30fbb762b6ba2abd2aece989c65f29 /home/pimania/ebooks/Decentralised Finance/dexes/Liquidity Provisioning - LemmaSwap.html 
https://gist.github.com/8a4c71e3a91a863d6d0db4e215968672 /home/pimania/ebooks/Decentralised Finance/dexes/CurveToken - Developer Docs.html 
https://gist.github.com/30b3c31826661607a189c7440255a787 /home/pimania/ebooks/Decentralised Finance/dexes/Automated Market Makers - saddle.finance.html 
https://gist.github.com/06fa5500d2858e268b10e9320dd1fa1c /home/pimania/ebooks/Decentralised Finance/dexes/Overview - DeltaPrime.html 
https://gist.github.com/64af20013e76e3629db63ec5cc76682f /home/pimania/ebooks/Decentralised Finance/dexes/CryptoSwap - Developer Docs.html 
https://gist.github.com/9a31352113a4a680c04a15096a7aca41 /home/pimania/ebooks/Decentralised Finance/dexes/vAMM - Developer Docs.html 
https://gist.github.com/a8cf80e9e4b34377460a504ed27a0ce3 /home/pimania/ebooks/Decentralised Finance/dexes/Saddle Pools - saddle.finance.html 
https://gist.github.com/34652c8a85926a8fe9937bed35aa4896 /home/pimania/ebooks/Decentralised Finance/dexes/V2 (B.AMM) - B.Protocol Docs.html 
https://gist.github.com/9cd513435d2deb406a3a56726d73db07 /home/pimania/ebooks/Decentralised Finance/dexes/Curve - Specification.html 
https://gist.github.com/2481cad49eec819fce4340ff4f883d98 /home/pimania/ebooks/Decentralised Finance/dexes/Liquidity - MUX.html 
https://gist.github.com/19e34303e84b931b4e87195c53e82390 /home/pimania/ebooks/Decentralised Finance/dexes/Swaps - LemmaSwap.html 
https://gist.github.com/d6bb120294d59a962cf41865eb8693b2 /home/pimania/ebooks/Decentralised Finance/dexes/Saddle Incentives - saddle.finance.html 
https://gist.github.com/62099bd8141b980bd705547d3be0bc5c /home/pimania/ebooks/Decentralised Finance/dexes/Tokenomics - MUX.html 
https://gist.github.com/10e50015f1f079cf015f0b4476964b4b /home/pimania/ebooks/Decentralised Finance/dexes/Saddle FAQ - saddle.finance.html 
https://gist.github.com/6d2e388717b17d8fcfc84c90373b08dc /home/pimania/ebooks/Decentralised Finance/dexes/Asset Specific Risks - saddle.finance.html 
https://gist.github.com/fe77f92f247082f95539a136a3215748 /home/pimania/ebooks/Decentralised Finance/dexes/Additional Risks - LemmaSwap.html 
https://gist.github.com/79c358515f4c5c9ec0d33e48c76701da /home/pimania/ebooks/Decentralised Finance/dexes/Community Pools - saddle.finance.html 
https://gist.github.com/e19129c4e96b7ffd11533afcf09881f9 /home/pimania/ebooks/Decentralised Finance/dexes/Sports AMM - Overtime Documentation.html 
https://gist.github.com/c8fa1f93e068ed6cb562c93249c7f943 /home/pimania/ebooks/Decentralised Finance/dexes/Auto-Deleveraging (ADL) - Futureswap Docs.html 
https://gist.github.com/318ed381cef7f1995b6a20ced89f8376 /home/pimania/ebooks/Decentralised Finance/dexes/SDL Token - saddle.finance.html 
https://gist.github.com/ec3e3cfc30c4a83700a0047c7c914532 /home/pimania/ebooks/Decentralised Finance/dexes/Multiplexing Layer - MUX.html 
https://gist.github.com/b3e62b17b276324fdae8730db47a582f /home/pimania/ebooks/Decentralised Finance/dexes/Build With Saddle - saddle.finance.html 
https://gist.github.com/148cba12a36feec1479f9ad6c89ba450 /home/pimania/ebooks/Decentralised Finance/dexes/Hybrid Orderbook AMM Design - Vertex Docs.html 
https://gist.github.com/495dbedea5d5c6e89761dfc644fc7757 /home/pimania/ebooks/Decentralised Finance/dexes/Deposit Liquidity - Chromatic Protocol.html 
https://gist.github.com/53f8c4b9b2341c84bda1eac8abe12b46 /home/pimania/ebooks/Decentralised Finance/dexes/Understanding Crypto Pools - Kokonut Swap.html 
https://gist.github.com/cfb16f7ddfc6203a3f1ebbeba5b789ae /home/pimania/ebooks/Decentralised Finance/dexes/Limit Order Book - Apex Docs.html 
https://gist.github.com/e3bc0b3e9308b2db8cf23cae70b350de /home/pimania/ebooks/Decentralised Finance/dexes/Comparison with order book exchanges - Apex Docs.html 
https://gist.github.com/e5df4c97adac6a979ad86915b360dbf4 /home/pimania/ebooks/Decentralised Finance/ml and computation/Bittensor Building Blocks - Bittensor.html 
https://gist.github.com/ee1d1819f6eb1201f981305f5e629364 /home/pimania/ebooks/Decentralised Finance/ml and computation/Anatomy of Incentive Mechanism - Bittensor.html 
https://gist.github.com/44e50c5eab83bf261411724c5f9eeeaf /home/pimania/ebooks/Decentralised Finance/opsec and privacy/What is HOPR - HOPR Docs.html 
https://gist.github.com/a876913b1826261a9a270bd393d90df4 /home/pimania/ebooks/Decentralised Finance/opsec and privacy/Mixnets - HOPR Docs.html 
https://gist.github.com/75a38f3cde4181dc0b17c48f39d66e6b /home/pimania/ebooks/Decentralised Finance/opsec and privacy/Anonymous Routing - HOPR Docs.html 
https://gist.github.com/1059807707cf755b830bc7d9faa14c06 /home/pimania/ebooks/Decentralised Finance/opsec and privacy/Cover Traffic Nodes - HOPR Docs.html 
https://gist.github.com/212081c622982e3fa8e2f7d9074dacd9 /home/pimania/ebooks/Decentralised Finance/opsec and privacy/Cover Traffic - HOPR Docs.html 
https://gist.github.com/f98757ada5538c29493e0496566177c8 /home/pimania/ebooks/Decentralised Finance/opsec and privacy/Balancing Cover Traffic - HOPR Docs.html 
https://gist.github.com/358a78421c81451270ca3ec01f7e415a /home/pimania/ebooks/Decentralised Finance/opsec and privacy/Proof of Relay - HOPR Docs.html 
https://gist.github.com/f51a8ef3ace9ecbd76f66dafbaa70793 /home/pimania/ebooks/Decentralised Finance/opsec and privacy/What is Metadata - HOPR Docs.html 
https://gist.github.com/8a728d5249dbc97ecac93b2bbba32436 /home/pimania/ebooks/Decentralised Finance/lending/isolated risk - pharos.html 
https://gist.github.com/9ee8733ca9b2d439e37dcf2c12721b71 /home/pimania/ebooks/Decentralised Finance/lending/example use - pharos.html 
https://gist.github.com/e5a3698106ce2aa1713592a907be0749 /home/pimania/ebooks/Decentralised Finance/lending/special uses - pharos.html 
https://gist.github.com/963aa8e18dca6ca1714d82f1709c58a1 /home/pimania/ebooks/Decentralised Finance/lending/What is Solv Protocol - Solv Documentation.html 
https://gist.github.com/bee9da3944861c73c46160e657cb16a5 /home/pimania/ebooks/Decentralised Finance/lending/Leverage 2.0 is composable! - Gearbox Protocol.html 
https://gist.github.com/787008be3f9db80569af77ee3121f4dd /home/pimania/ebooks/Decentralised Finance/lending/Economic Risks - Mai Finance.html 
https://gist.github.com/266688691b7fc6099d6dd0b872d7dd03 /home/pimania/ebooks/Decentralised Finance/lending/Borrowing - DeltaPrime.html 
https://gist.github.com/ba12fcfd4932df51b19f600caaa306cb /home/pimania/ebooks/Decentralised Finance/lending/Fees - Futureswap Docs.html 
https://gist.github.com/7efd36314736ca71dd73ed41dccfd516 /home/pimania/ebooks/Decentralised Finance/lending/Borrower - Fungify.html 
https://gist.github.com/160fe7fb3b43972f110f48494360e05c /home/pimania/ebooks/Decentralised Finance/lending/Risk Framework - Portal.html 
https://gist.github.com/e49c3b76f8db2c3e1e51cf53d7e065f5 /home/pimania/ebooks/Decentralised Finance/lending/Liquidation FAQ - Portal.html 
https://gist.github.com/f0cb83e7996c8b60bea056d1196e83d6 /home/pimania/ebooks/Decentralised Finance/lending/True Ownership - Portal.html 
https://gist.github.com/28847c29990cf3a4ba7c4e7038718e67 /home/pimania/ebooks/Decentralised Finance/lending/Security - Mai Finance.html 
https://gist.github.com/68af68d876ef19ee1a36be2013f80a4d /home/pimania/ebooks/Decentralised Finance/lending/NFT Risk Parameters - Portal.html 
https://gist.github.com/fc320a5aeddf41fedba4d2b71b1e5b1a /home/pimania/ebooks/Decentralised Finance/lending/Liquidation - Developer Docs 1.html 
https://gist.github.com/0695c1f65614374d461fb6de6a5691ce /home/pimania/ebooks/Decentralised Finance/lending/Reserve Risk Parameters - Portal.html 
https://gist.github.com/f832b0854f6da0e7a1750e6a08e12f98 /home/pimania/ebooks/Decentralised Finance/lending/Liquidations - Futureswap Docs.html 
https://gist.github.com/ab43714d11c856e226b8ca4e361e3879 /home/pimania/ebooks/Decentralised Finance/lending/Security FAQ - Portal.html 
https://gist.github.com/0d01f9a7c5c0c38bd600eebb067eb596 /home/pimania/ebooks/Decentralised Finance/lending/Risks - Futureswap Docs.html 
https://gist.github.com/553fccb43fb0e4a1f1ce1b4a94c8fa46 /home/pimania/ebooks/Decentralised Finance/lending/Economic Soundness - Futureswap Docs.html 
https://gist.github.com/f7918c648f7cccc7afbf1f7098309197 /home/pimania/ebooks/Decentralised Finance/lending/Liquidations - DeltaPrime.html 
https://gist.github.com/4761d6a26a994e9c405f89a8f4249f57 /home/pimania/ebooks/Decentralised Finance/lending/Debt Ceilings - Mai Finance.html 
https://gist.github.com/0605c2edd83a6b4e181ce0bf63a36ed1 /home/pimania/ebooks/Decentralised Finance/lending/Controlled Risks - Mai Finance.html 
https://gist.github.com/dc06a2681a1c4e4089bba567e04a97fc /home/pimania/ebooks/Decentralised Finance/lending/MarketVault - Fungify.html 
https://gist.github.com/479a68ccf243b1c14b2a49992ac18108 /home/pimania/ebooks/Decentralised Finance/lending/Borrowing and lending - contango.html 
https://gist.github.com/9ad41f6b47e996c3448e38a8392b88cc /home/pimania/ebooks/Decentralised Finance/lending/Trading Flow - Futureswap Docs.html 
https://gist.github.com/0f7845c8c9300bf0552382b3eff9938e /home/pimania/ebooks/Decentralised Finance/lending/Borrowing - Beta Finance.html 
https://gist.github.com/8f452a08e7f078f8ae568d5387221e8e /home/pimania/ebooks/Decentralised Finance/lending/Liquidations - Fungify.html 
https://gist.github.com/3e6dc7d3b1dfe3d3629815e870225efb /home/pimania/ebooks/Decentralised Finance/lending/Unlock the Blockchain - DeltaPrime.html 
https://gist.github.com/f699e150db6fd8e00047e2a564b2558a /home/pimania/ebooks/Decentralised Finance/lending/Risks - Yama Finance.html 
https://gist.github.com/0e98c8b8a992510349b31ca6a5aea197 /home/pimania/ebooks/Decentralised Finance/lending/Lender First Pool - Vendor Finance V2 Developer Documentation.html 
https://gist.github.com/f454a639e2bb8b079117d63d98012b94 /home/pimania/ebooks/Decentralised Finance/lending/Oracle - Vendor Finance V2 Developer Documentation.html 
https://gist.github.com/234dd70305a963053cfd635cf0fe930d /home/pimania/ebooks/Decentralised Finance/lending/Blitz Match (P2P) Borrowing & Lending - MYSO v2 Docs.html 
https://gist.github.com/98f954e903367b4b0b6dd96a9efb67a9 /home/pimania/ebooks/Decentralised Finance/lending/Whale Match (P2Pool) Borrowing & Lending - MYSO v2.html 
https://gist.github.com/be1c6437487c54aed922a28da0528cad /home/pimania/ebooks/Decentralised Finance/lending/Fair Pricing Considerations - MYSO v2 Docs.html 
https://gist.github.com/51c998d46242eb70379ae0d92f3fefb0 /home/pimania/ebooks/Decentralised Finance/lending/Liquidations & Insurance Fund - Vertex Docs.html 
https://gist.github.com/f1a0c81d211d8a6de7bdb4bd715a2853 /home/pimania/ebooks/Decentralised Finance/lending/Blitz Match FAQs - MYSO v2 Docs.html 
https://gist.github.com/c4030978d8aa2d21bf3f528cf1536d04 /home/pimania/ebooks/Decentralised Finance/lending/Pricing Loans - MYSO v2 Docs.html 
https://gist.github.com/766c8993100c42a62ca77bede82a6f5e /home/pimania/ebooks/Decentralised Finance/lending/Lenders - MYSO v2 Docs.html 
https://gist.github.com/b93a82086056ca47e3c364fe832da924 /home/pimania/ebooks/Decentralised Finance/lending/Payoffs - MYSO v2 Docs.html 
https://gist.github.com/fb0119e702d38f04e80e2f1f90828631 /home/pimania/ebooks/Decentralised Finance/lending/Fair APRs - MYSO v2 Docs.html 
https://gist.github.com/67b8b63a2b659882c4a19963f99705d1 /home/pimania/ebooks/Decentralised Finance/lending/Borrowers - MYSO v2 Docs.html 
https://gist.github.com/999881a4c01ad1b887595e1508fa4ff9 /home/pimania/ebooks/Decentralised Finance/lending/Introduction - Introduction.html 
https://gist.github.com/ff305f8671877ffbac9ab0085f930b2e /home/pimania/ebooks/Decentralised Finance/lending/Lending and Borrowing - Introduction.html 
https://gist.github.com/4617eec4bf9a7af721ad213ba74ab8b4 /home/pimania/ebooks/Decentralised Finance/lending/Gauge system - Introduction.html 
https://gist.github.com/307337b6a646c27eaf1a85893bc32e6f /home/pimania/ebooks/Decentralised Finance/lending/Auctions - Introduction.html 
https://gist.github.com/4517b2c3dcd26d13edfd2a64a4053be4 /home/pimania/ebooks/Decentralised Finance/lending/Propose a Lending Term - Introduction.html 
https://gist.github.com/56f2de2f33909d527e3677229ada5e08 /home/pimania/ebooks/Decentralised Finance/lending/Staking - Introduction.html 
https://gist.github.com/a0355b1f4ce34875987cf7044fed71bd /home/pimania/ebooks/Decentralised Finance/lending/Governance - Introduction.html 
https://gist.github.com/b3df940f35dbafe6ae27d27e3b714427 /home/pimania/ebooks/Decentralised Finance/lending/How it Works - Timeswap.html 
https://gist.github.com/3e700cff2c80bc8a383706c6fa7f61cc /home/pimania/ebooks/Decentralised Finance/lending/Use Cases - Timeswap.html 
https://gist.github.com/38eeb7d7f6c79e160fb5a75e007d705b /home/pimania/ebooks/Decentralised Finance/futures, margin and perps/Liquidity on V2 - GMX Docs.html 
https://gist.github.com/15fe68f5e993722e603332a446c3700a /home/pimania/ebooks/Decentralised Finance/futures, margin and perps/Pool Reserves - Duality Documentation.html 
https://gist.github.com/79f431f275ff5d7edec928b8ff3a29c3 /home/pimania/ebooks/Decentralised Finance/futures, margin and perps/📑 Litepaper - ApeX Pro.html 
https://gist.github.com/fb8fcd5a786ac4874d90c8779490f507 /home/pimania/ebooks/Decentralised Finance/futures, margin and perps/Funding Fees - ApeX Pro.html 
https://gist.github.com/8f91484e168eeb9aeac2acbc8059e8d3 /home/pimania/ebooks/Decentralised Finance/futures, margin and perps/Core Concepts - Increment.html 
https://gist.github.com/34ecf1736e529772cd1ae072e654f724 /home/pimania/ebooks/Decentralised Finance/futures, margin and perps/Funding payments - Developer Docs.html 
https://gist.github.com/7f50501b40df113ea8f8f8072be8f054 /home/pimania/ebooks/Decentralised Finance/futures, margin and perps/Margin - Developer Docs.html 
https://gist.github.com/04a3877d6e2cd8919b444cbfb46983e5 /home/pimania/ebooks/Decentralised Finance/futures, margin and perps/Position opening - contango.html 
https://gist.github.com/c54329b1b8684a8fe959b4e858ad277c /home/pimania/ebooks/Decentralised Finance/futures, margin and perps/Shorting - Beta Finance.html 
https://gist.github.com/b5cc375039b4c66c2b92a4df086ca537 /home/pimania/ebooks/Decentralised Finance/futures, margin and perps/How it works - contango.html 
https://gist.github.com/9607c50e677299254f466ebf01141a04 /home/pimania/ebooks/Decentralised Finance/futures, margin and perps/Use cases - contango.html 
https://gist.github.com/f15906c196fd974227ef075f26caa900 /home/pimania/ebooks/Decentralised Finance/futures, margin and perps/Theoretical pricing - contango.html 
https://gist.github.com/305770b0ccf1064762d68e64abe1b566 /home/pimania/ebooks/Decentralised Finance/futures, margin and perps/Price improvement - contango.html 
https://gist.github.com/7dc808f012691683c6df6e74fc0470ad /home/pimania/ebooks/Decentralised Finance/futures, margin and perps/Equity management - contango.html 
https://gist.github.com/72079306f2138a6438714a83e2e3d2f7 /home/pimania/ebooks/Decentralised Finance/futures, margin and perps/Protocol pricing - contango.html 
https://gist.github.com/d5d00518a5c6ed91f9949296c433ae3e /home/pimania/ebooks/Decentralised Finance/futures, margin and perps/Overview - Rage Trade.html 
https://gist.github.com/dbc6e13a7936e30e5943761482d4704e /home/pimania/ebooks/Decentralised Finance/futures, margin and perps/Funding - Specification.html 
https://gist.github.com/203830a9d6015f948144f6f4fa3d4686 /home/pimania/ebooks/Decentralised Finance/futures, margin and perps/Position closing - contango.html 
https://gist.github.com/5be838e9c39322147c9bef4047b1445a /home/pimania/ebooks/Decentralised Finance/futures, margin and perps/Perpetual Yield Token (PYT) - Timeless Docs.html 
https://gist.github.com/16bf073ed893fdcf8b06717ebffdbe54 /home/pimania/ebooks/Decentralised Finance/futures, margin and perps/Comparing capital efficiency - SYMMIO Protocol Gitbook.html 
https://gist.github.com/1a9ce0832144a48373c5b625e949e6fb /home/pimania/ebooks/Decentralised Finance/futures, margin and perps/Section I. - Introduction - SYMMIO Protocol Gitbook.html 
https://gist.github.com/2a44e660f8c14f2fbc04c3dbf5897adb /home/pimania/ebooks/Decentralised Finance/futures, margin and perps/Section III. - Solutions - SYMMIO Protocol Gitbook.html 
https://gist.github.com/9d5147211290e0e7d28f37d66a9130f7 /home/pimania/ebooks/Decentralised Finance/futures, margin and perps/Section V. FC (open) - SYMMIO Protocol Gitbook.html 
https://gist.github.com/142d70998692e8ab87ed4ab070424857 /home/pimania/ebooks/Decentralised Finance/futures, margin and perps/Section II - A Case Study - SYMMIO Protocol Gitbook.html 
https://gist.github.com/a1296f21b035efb8d1ad9f4187c00c2d /home/pimania/ebooks/Decentralised Finance/futures, margin and perps/Part I. - SYMMIO Protocol Gitbook.html 
https://gist.github.com/57313b348e2bcc3d5a239b01047a80a8 /home/pimania/ebooks/Decentralised Finance/futures, margin and perps/Section IV. - FC (oracle) - SYMMIO Protocol Gitbook.html 
https://gist.github.com/8c900edaba690f972dbc03e6cad4916a /home/pimania/ebooks/Decentralised Finance/futures, margin and perps/Part II. - SYMMIO Protocol Gitbook.html 
https://gist.github.com/6c163793ac344e5681f491b358a1a135 /home/pimania/ebooks/Decentralised Finance/futures, margin and perps/Part III. - SYMMIO Protocol Gitbook.html 
https://gist.github.com/d301fe44d54ff1381be61816716bb2a7 /home/pimania/ebooks/Decentralised Finance/futures, margin and perps/Part V. - SYMMIO Protocol Gitbook.html 
https://gist.github.com/a7dce0b3cafa09433bddf6b672ddfe14 /home/pimania/ebooks/Decentralised Finance/futures, margin and perps/Part IV. - SYMMIO Protocol Gitbook.html 
https://gist.github.com/aff8091bf67f1f8193dc6475e06d453e /home/pimania/ebooks/Decentralised Finance/futures, margin and perps/Products - Vertex Docs.html 
https://gist.github.com/d34e9cdf32177a84b64386f213e05bad /home/pimania/ebooks/Decentralised Finance/futures, margin and perps/Universal Cross Margin - Vertex Docs.html 
https://gist.github.com/ccb4f43ac04bd79174e7f7ee90c80c92 /home/pimania/ebooks/Decentralised Finance/futures, margin and perps/PnL Settlements - Vertex Docs.html 
https://gist.github.com/ac23e3f5fbca9d60413fa161faae4dfe /home/pimania/ebooks/Decentralised Finance/futures, margin and perps/Funding Rates - Vertex Docs.html 
https://gist.github.com/6b7cf9422de74fb48181411ae85e237b /home/pimania/ebooks/Decentralised Finance/futures, margin and perps/Hyperliquid L1 - Hyperliquid Docs.html 
https://gist.github.com/ce330feb709436ffa4c963584ce27e72 /home/pimania/ebooks/Decentralised Finance/futures, margin and perps/Order book - Hyperliquid Docs.html 
https://gist.github.com/7d23a8bc009cf3d2d525aacf2f22f85e /home/pimania/ebooks/Decentralised Finance/futures, margin and perps/API servers - Hyperliquid Docs.html 
https://gist.github.com/7b866b086f500182c6540188aa13c3d8 /home/pimania/ebooks/Decentralised Finance/futures, margin and perps/Hyperps - Hyperliquid Docs.html 
https://gist.github.com/4c45f524edaa24e9600af90e19c9ee15 /home/pimania/ebooks/Decentralised Finance/futures, margin and perps/The Basics of Perpetual Futures and Perpetual Protocol.html 
https://gist.github.com/756b3630bbc12b4f6e2ea8275f0cbd4b /home/pimania/ebooks/Decentralised Finance/futures, margin and perps/APEX Limit Order Design - Apex Docs.html 
https://gist.github.com/495dbedea5d5c6e89761dfc644fc7757 /home/pimania/ebooks/Decentralised Finance/futures, margin and perps/Deposit Liquidity - Chromatic Protocol_1.html 
https://gist.github.com/a7139942d49544e3b1a2bf291453e913 /home/pimania/ebooks/Decentralised Finance/nfts/Introduction - Fungify.html 
https://gist.github.com/3f12bf8f3b27a37ac86c0aedb170f8d8 /home/pimania/ebooks/Decentralised Finance/prediction markets/Get ready for Overtime - Overtime Documentation.html 
https://gist.github.com/a0ae9aa75608e6f927d734c6adcc47a9 /home/pimania/ebooks/Decentralised Finance/prediction markets/Whitepaper - Thales Documentation.html 
https://gist.github.com/9a0f14c19532ad6d6fe600f358d75538 /home/pimania/ebooks/Decentralised Finance/prediction markets/Market Creation - Overtime Documentation.html 
https://gist.github.com/43454ca4a9292bb1a3a56e04b0f57fa7 /home/pimania/ebooks/Decentralised Finance/interest rate derivs/Negative Yield Token (NYT) - Timeless Docs.html 
https://gist.github.com/feed42c5a9fee04fbc61eb756efa958f /home/pimania/ebooks/Decentralised Finance/interest rate derivs/Yield Hedging - Timeless Docs.html 
https://gist.github.com/b5945cf050894d105f07883e920367b2 /home/pimania/ebooks/Decentralised Finance/interest rate derivs/Swapping - Timeless Docs.html 
https://gist.github.com/20a10ec3682009be218f0f1ab5983a2c /home/pimania/ebooks/Decentralised Finance/interest rate derivs/Compounded Perpetual Yield Token (xPYT) - Timeless.html 
https://gist.github.com/1f972fc822a98250ea1ee97cabf8801f /home/pimania/ebooks/Decentralised Finance/interest rate derivs/Core Concepts - Sense.html 
https://gist.github.com/d8a7f08f19c1cfd17d6987096f90f872 /home/pimania/ebooks/Decentralised Finance/interest rate derivs/Yield Boosting - Timeless Docs.html 
https://gist.github.com/434079530d2a9b5800298b0869c460da /home/pimania/ebooks/Decentralised Finance/interest rate derivs/Yield Speculation - Timeless Docs.html 
https://gist.github.com/1adb4b53b4dceb499467725af746784e /home/pimania/ebooks/Decentralised Finance/interest rate derivs/Yield Tokenization - Timeless Docs.html 
https://gist.github.com/61ff31b028cc5cd5cc1c25707c443b0b /home/pimania/ebooks/Decentralised Finance/interest rate derivs/Why Sense - Sense.html 
https://gist.github.com/ccf35582d8e1c5b36a06511a9dcb889c /home/pimania/ebooks/Decentralised Finance/interest rate derivs/What is Timeless - Timeless Docs.html 
https://gist.github.com/d0883d05854b4c8c20b3bae1e65f49ae /home/pimania/ebooks/Decentralised Finance/interest rate derivs/FAQs - Sense.html 
https://gist.github.com/ce1c0addefd82dcbb0bcf9530f1e3dff /home/pimania/ebooks/Decentralised Finance/auctions and mev/Multiplicity - Duality Documentation.html 
https://gist.github.com/9ad3142270c6bd3df26eba44a27c19db /home/pimania/ebooks/Decentralised Finance/auctions and mev/Comprehensive Compute Fees - Solana Docs.html 
https://gist.github.com/26b33190a1bf61f8a6acd84c9b8e087a /home/pimania/ebooks/Decentralised Finance/auctions and mev/Fee Transaction Priority - Solana Docs.html 
https://gist.github.com/1841bddd0882adcbed198f4841996823 /home/pimania/ebooks/Decentralised Finance/auctions and mev/Developer Guide - Apex Docs.html 
https://gist.github.com/75428df8a8899c45f5393c62968894d8 /home/pimania/ebooks/Decentralised Finance/auctions and mev/Smart Wallet - Apex Docs.html 
https://gist.github.com/ce5971d0fe26cb4464d094a14a57d6a5 /home/pimania/ebooks/Decentralised Finance/stablecoins and synths/Minting - Lybra Finance Docs.html 
https://gist.github.com/821efb4ad3c8d633db586c111e72eb0e /home/pimania/ebooks/Decentralised Finance/stablecoins and synths/Interest-Bearing Stablecoin - Lybra Finance Docs.html 
https://gist.github.com/a58b2dac3f8380fe33747a021538fedf /home/pimania/ebooks/Decentralised Finance/stablecoins and synths/How can eUSD stability be ensured - Lybra Finance.html 
https://gist.github.com/2030835036ebd31daf7d79524ef8e5d5 /home/pimania/ebooks/Decentralised Finance/stablecoins and synths/Collateral Assets - Mai Finance.html 
https://gist.github.com/d28fc90e681ff492808cc4c7dd13a3de /home/pimania/ebooks/Decentralised Finance/stablecoins and synths/What is LBR - Lybra Finance Docs.html 
https://gist.github.com/69da049cab36924f47e526cf451cde13 /home/pimania/ebooks/Decentralised Finance/stablecoins and synths/What Properties of eUSD Function Similarly to Money.html 
https://gist.github.com/f895cffebe22a3afb1831c7ebd2be526 /home/pimania/ebooks/Decentralised Finance/stablecoins and synths/How does eUSD generate interest - Lybra Finance Docs.html 
https://gist.github.com/e5f72cc063fca0b2e642fddc6ca2f9ee /home/pimania/ebooks/Decentralised Finance/stablecoins and synths/Rigid Redemption and eUSD Price Stability - Lybra.html 
https://gist.github.com/0eb89360af1e23964e20120ba66f5694 /home/pimania/ebooks/Decentralised Finance/stablecoins and synths/Liquidation - Lybra Finance Docs.html 
https://gist.github.com/7a7fd1e97a8f395a452d30efafd49e22 /home/pimania/ebooks/Decentralised Finance/stablecoins and synths/ESM - GEB Docs.html 
https://gist.github.com/3472672da808a35d519e5acf22faa049 /home/pimania/ebooks/Decentralised Finance/stablecoins and synths/Technical Summary - Yama Finance.html 
https://gist.github.com/9a018a47fafc1c6b0615bc30e4d67905 /home/pimania/ebooks/Decentralised Finance/stablecoins and synths/The Story Behind Yama - Yama Finance.html 
https://gist.github.com/d48120eda1cbd92242cbc6b547f56cba /home/pimania/ebooks/Decentralised Finance/stablecoins and synths/Synthetic Tokens - LemmaSwap.html 
https://gist.github.com/4d6d9cbf83ff118cca9d117081640e6a /home/pimania/ebooks/Decentralised Finance/stablecoins and synths/USDL - Lemma.html 
https://gist.github.com/de75cd0a158177a63c21013fb414cc67 /home/pimania/ebooks/Decentralised Finance/stablecoins and synths/Synthetix Litepaper - Synthetix Docs.html 
https://gist.github.com/efeba65c1d3918c9c819d924cc1f8eb4 /home/pimania/ebooks/Decentralised Finance/stablecoins and synths/How Does it Work Stablecoin Economics - Mai Finance.html 
https://gist.github.com/913bc4399d3f44849ac80b4f667a7f54 /home/pimania/ebooks/Decentralised Finance/stablecoins and synths/Reasoning - DeltaPrime.html 
https://gist.github.com/69bd6d7fad15f2c612ce3337be6e4719 /home/pimania/ebooks/Decentralised Finance/stablecoins and synths/PID Failure Modes & Responses - GEB Docs.html 
https://gist.github.com/0c879ebfe2cdb89cce3b29fa639a1f6b /home/pimania/ebooks/Decentralised Finance/stablecoins and synths/Governance Minimization Guide - GEB Docs.html 
https://gist.github.com/839ce4607f60f835732f3928bcf9cf56 /home/pimania/ebooks/Decentralised Finance/stablecoins and synths/Introduction - Abracadabra.html 
https://gist.github.com/8da108221f1f5a3dddcd4bcdc38d5934 /home/pimania/ebooks/Decentralised Finance/stablecoins and synths/GEB Risks - GEB Docs.html 
https://gist.github.com/d1a2d45d926d1dbe4158a312761bd945 /home/pimania/ebooks/Decentralised Finance/stablecoins and synths/Synthetic Asset Model - THORChain Docs.html 
https://gist.github.com/9b576eecf4e58141a245d273dbaa71bc /home/pimania/ebooks/Decentralised Finance/stablecoins and synths/Understanding Stable Swap - Kokonut Swap.html 
https://gist.github.com/11f325149d6c7ca3212b8d9815c6cff9 /home/pimania/ebooks/Decentralised Finance/zk and cryptography/Jiritsu- ZK Automation for Smart Contract - Jiritsu.html 
https://gist.github.com/d24c9df96f65ba0e301fcc712018fcb4 /home/pimania/ebooks/Decentralised Finance/zk and cryptography/Group Generators - Sismo Docs.html 
https://gist.github.com/7269c0f552bfbad58851222f3de14730 /home/pimania/ebooks/Decentralised Finance/zk and cryptography/What is Sismo - Sismo Docs.html 
https://gist.github.com/00260bd083b70e67c7f60ae6dc95a5d7 /home/pimania/ebooks/Decentralised Finance/zk and cryptography/How zkApps Work - Mina Protocol.html 
https://gist.github.com/02c38e724b9053f1fae6cd215fe93987 /home/pimania/ebooks/Decentralised Finance/zk and cryptography/Frequently Asked Questions - HOPR Docs.html 
https://gist.github.com/e56281ae69f3064a04e3755b8fc4e2f3 /home/pimania/ebooks/Decentralised Finance/zk and cryptography/What are zkApps - Mina Protocol.html 
https://gist.github.com/db810783669bad0057cab21f7d762dac /home/pimania/ebooks/Decentralised Finance/zk and cryptography/Incentives - HOPR Docs.html 
https://gist.github.com/e50eca56f8ea713a89f1a0bf70c20626 /home/pimania/ebooks/Decentralised Finance/zk and cryptography/Important Account abstraction support - zkSync secure.html 
https://gist.github.com/a79eea0896cf44214dbe2e3fd4530f51 /home/pimania/ebooks/Decentralised Finance/oracles/Median - Detailed Documentation - Maker Protocol.html 
https://gist.github.com/cf6414c65f096ecdb9fae012632c0d1c /home/pimania/ebooks/Decentralised Finance/oracles/Oracle Security Module (OSM) - Detailed Documentation.html 
https://gist.github.com/a5097b7579e3038b2214eb46aa5b3cc1 /home/pimania/ebooks/Decentralised Finance/oracles/.Price Oracle Solution for Unbound - Unbound.Finance.html 
https://gist.github.com/2b6b902fd84ae27e5031b33e422467e0 /home/pimania/ebooks/Decentralised Finance/oracles/.Economics - Adrastia Docs.html 
https://gist.github.com/994f5730e74fb7f735cd2e30cbd16642 /home/pimania/ebooks/Decentralised Finance/oracles/.Attack Vectors - Adrastia Docs.html 
https://gist.github.com/dfb80508a5abbf166a9b6ca873e209ba /home/pimania/ebooks/Decentralised Finance/oracles/Pricing (Oracles) - Vertex Docs.html 
https://gist.github.com/c2675c6ce84f67a34e5e214ab55c4758 /home/pimania/ebooks/Decentralised Finance/oracles/Oracle - Hyperliquid Docs.html 
"""


gistUrlToFileNamePairs = {}

for gistUrl in gitBooksToAdd.strip().split("\n"):
    url = gistUrl.split(" ")[0]
    fileName = " ".join(gistUrl.split(" ")[1:])
    bad = False
    for gitBookToDelete in gitBooksToDelete:
        if gitBookToDelete in url:
            bad = True
    if not bad:
        gistUrlToFileNamePairs[url] = fileName
print("\n\n\n\n\n\n")
print(gistUrlToFileNamePairs)
