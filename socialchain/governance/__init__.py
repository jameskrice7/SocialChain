"""Governance module for decentralized community self-governance.

Inspired by Ehud Shapiro's work on digital democracy and social contracts,
this module provides proposal creation, voting mechanisms, and community
management for self-sovereign communities on the SocialChain network.
"""
from .proposal import Proposal, ProposalStatus, ProposalType
from .voting import VotingSystem, VoteChoice, VotingMethod
from .community import Community, CommunityRole, Membership

__all__ = [
    "Proposal", "ProposalStatus", "ProposalType",
    "VotingSystem", "VoteChoice", "VotingMethod",
    "Community", "CommunityRole", "Membership",
]
