# Account Creation and First-Use Setup

## Overview

This update adds self-service account creation to the authentication experience. A new user can create an owner account, organization, and initial reliability workspace before signing in or using any platform feature.

## Registration Workflow

The registration form collects the user’s name, work email, password, organization name, and workspace name. Successful registration creates all required tenancy records atomically and signs the new owner into the platform immediately.

## Ownership and Workspace Setup

The first account created through registration becomes the organization owner. The platform creates an active workspace and uses it as the account’s current workspace. Additional users continue to join through the existing invitation workflow.

## Security and Validation

Passwords are salted and hashed using PBKDF2-SHA256. Duplicate email addresses are rejected, session cookies remain HTTP-only, and organization and workspace slugs are generated uniquely.

## First-Use Validation

The registration flow is now the starting point for the standard end-to-end platform test, followed by login, workspace validation, team invitations, dataset import, auditing, rules, contracts, and issue management.
