"""Connection layer between Medicus OS and the Norwegian health network.

Everything in Medicus talks to the health network through `helsenett.client.get_client()`.
Today that returns a client for the local simulator. If an agreement with Norsk helsenett
(NHN) is made, the same interface is backed by the real services by changing one setting.
See docs/helsenorge-integrasjon.md.
"""
