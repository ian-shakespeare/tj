# TJ

> Travel Japan!

An AI-powered Japan travel planner.

## Getting Started

Start docker services and development server

```sh
make up run
```

Create a super user

```sh
make superuser
```

The server is now accessible at [localhost:8000](http://localhost:8000)

## Usage

> [!TIP]
> Admins may add relevant documents to the RAG database for better trip plans on the [document upload page](http://localhost:8000/documents/new).

To kick off a new trip plan generation, visit the [new plan page](http://localhost:8000/plans/new).

Once a plan has finished generation you will receive an email. You may then view your plans on the [plan list page](http://localhost:8000/plans). Simply select a plan to view it.

## Disclaimer

This app is NOT production ready.
This app is for experimental use only.
This app executes LLM generated code without any sanitation or sandboxxing which is HIGHLY insecure.
