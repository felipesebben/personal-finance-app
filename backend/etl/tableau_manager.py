import tableauserverclient as TSC
import os

class TableauManager:
    def __init__(self):
        """
        Initialize the manager by loading credentials
        We don't connect yet; just set up the configuration.
        """
        self.server_url = os.getenv("TABLEAU_SERVER_URL")
        self.site_name = os.getenv("TABLEAU_SITENAME")
        self.token_name = os.getenv("TABLEAU_TOKEN_NAME")
        self.token_value = os.getenv("TABLEAU_TOKEN_VALUE")

        self.server = None
        self.auth = None

    def connect(self):
        """
        Establishes the connection to Tableau Cloud.
        """
        if not all([self.server_url, self.site_name, self.token_name, self.token_value]):
            raise ValueError("Missing Tableau credentials in .env")
        
        self.auth = TSC.PersonalAccessTokenAuth(
            token_name=self.token_name,
            personal_access_token=self.token_value,
            site_id=self.site_name
        )
        self.server = TSC.Server(self.server_url, use_server_version=True)

        # Actually sign in
        self.server.auth.sign_in(self.auth)
        print(f"Logged into Tableau as {self.site_name}")

    def get_or_create_project(self, project_name: str):
        """
        The logic:
        1. Checks if `project_name` exists.
        2. If yes, returns its ID.
        3. If no, creates it and returns the new ID.
        
        :param project_name: Name of the project
        :type project_name: str
        """

        # Get all projects on the site
        all_projects, _ = self.server.projects.get()

        # Look for a match
        existing_project = next((p for p in all_projects if p.name == project_name), None)

        if existing_project:
            print(f"Found existing project: {project_name}")
            return existing_project.id
        else:
            print(f"Project {project_name} not found. Creating it...")
            new_project = TSC.ProjectItem(name=project_name)
            # Create returns the project item including the new ID
            new_project = self.server.projects.create(new_project)
            print(f"Successfully created project {project_name}")
            return new_project.id
        
    def publish_hyper(self, hyper_file_path :str, target_project_name:str="default"):
        """
        Docstring for publish_hyper
        
        :param hyper_file_path: Path to `hyper` file.
        :type hyper_file_path: str
        :param targer_project_name: Project Name
        :type targer_project_name: str
        """
        try:
            # 1. Sign in (if not already)
            if not self.server or not self.server.auth_token:
                self.connect()
            
            # 2. Get the Project ID (Creating it if necessary)
            project_id = self.get_or_create_project(target_project_name)

            # 3. Publish
            print(f"Uploading {hyper_file_path}...")
            datasource = TSC.DatasourceItem(project_id)

            published_item = self.server.datasources.publish(
                datasource,
                hyper_file_path,
                "Overwrite"
            )
            print(f"Success! Datasource {published_item.name} is live.")
            print(f"ID: {published_item.id}")
        except Exception as e:
            print(f"Publishing failed: {e}")
            raise e