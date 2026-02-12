"""Sample texts for testing RefWeaver.

These are example academic manuscript excerpts that can be used
for development and testing of the reference analysis pipeline.
"""

# Sample introduction paragraph from a fictional chemistry/biotech paper
# Contains a mix of:
# - Established facts (likely don't need references)
# - Specific claims that DO need references
# - Statistics and quantitative claims

SAMPLE_INTRODUCTION = """The LRLLR cell-penetrating motif can be transferred to confer membrane translocation activity, but only to compatible recipient peptides. Using umbrella sampling molecular dynamics simulations, we demonstrate that C-terminal LRLLR addition to the pro-apoptotic smacN peptide eliminates its translocation barrier entirely, transforming a +65 kJ/mol barrier into a −50 kJ/mol energy well. In contrast, N-terminal LRLLR addition to the neuroprotective NR2B9c peptide increases the translocation barrier from +85 to +100 kJ/mol, demonstrating that motif transfer can prove counterproductive for incompatible sequences. toxicity profiles. Carbon nanotubes and graphene oxide have both been explored as enzyme supports, though their large-scale synthesis remains economically challenging. The cost of producing pharmaceutical-grade graphene oxide can exceed $500 per gram, making widespread clinical adoption difficult without significant process improvements.
"""

MULTIPLE_PARAGRAPH_SAMPLE = """Cell-penetrating peptides offer promising strategies for intracellular delivery of therapeutic cargo, yet the sequence determinants governing their activity remain incompletely understood. The LRLLR motif, identified through systematic screening as essential for spontaneous membrane translocation, represents a minimal penetrating element whose transferability has not been previously evaluated. We appended this motif to two clinically relevant peptides: smacN, a tetrapeptide targeting inhibitor of apoptosis proteins in chemotherapy-resistant cancers, and NR2B9c, a nonapeptide that disrupts excitotoxic signaling in ischemic stroke.

Potential of mean force profiles calculated across a POPC/POPG bilayer, combined with analysis of hydrogen bonding patterns, secondary structure propensity, and conformational dynamics, reveal the structural basis for these divergent outcomes. Successful transfer to smacN results from favorable complementarity: the hydrophobic, neutral smacN provides an ideal platform for the charged, amphipathic LRLLR motif, yielding a chimera capable of simultaneous interaction with both membrane leaflets. Transfer failure with NR2B9c stems from conformational rigidity induced by intramolecular hydrogen bonding, which prevents optimal membrane insertion, combined with unfavorable positioning of internal polar residues at the bilayer center.
"""

# A shorter sample with clear reference needs
SHORT_SAMPLE = """Climate change has accelerated glacier retreat globally. The Greenland ice sheet lost approximately 280 gigatons of mass per year between 2002 and 2016. This rate of melting is unprecedented in at least the last 1,000 years according to ice core records. Rising sea levels threaten coastal communities worldwide, with projections suggesting up to 1 meter of sea level rise by 2100. Sea levels have been falling steadily for decades.
"""

# Sample with tricky sentence boundaries (abbreviations, decimals)
TRICKY_SAMPLE = """Dr. Johnson visited Washington D.C. on Jan. 15, 2024. The meeting started at 3:30 p.m. and lasted 2.5 hours. Prof. Smith (Ph.D.) presented findings from the U.S.A. study. The pH was measured at 7.4, i.e., neutral conditions. Results showed 99.9% purity, with an R² of 0.98. The company reported $1.5 million in Q4 revenue, up 25% from Q3.
"""

__all__ = [
    "SAMPLE_INTRODUCTION",
    "SHORT_SAMPLE",
    "TRICKY_SAMPLE",
]
