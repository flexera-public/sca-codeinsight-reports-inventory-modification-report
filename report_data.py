'''
Copyright 2023 Flexera Software LLC
See LICENSE.TXT for full license text
SPDX-License-Identifier: MIT

Author : sgeary  
Created On : Fri Aug 11 2023
File : report_data.py
'''
import logging
from collections import OrderedDict
import common.api.project.get_child_projects
import common.api.project.get_project_information
import common.api.project.get_project_inventory
import common.api.inventory.get_inventory_history
import common.api.users.search_users

logger = logging.getLogger(__name__)
logging.getLogger("urllib3").setLevel(logging.WARNING)  # Disable logging for requests module

#-------------------------------------------------------------------#
def gather_data_for_report(baseURL, projectID, authToken, reportName, reportOptions):
    logger.info("Entering gather_data_for_report")

    # Parse report options
    includeChildProjects = reportOptions["includeChildProjects"]  # True/False

    projectList = [] # List to hold parent/child details for report
    inventoryDetails = {} # Hold the event data for a specific inventory Item
    applicationDetails = {} # Dictionary to allow a project to be mapped to an application name/version

    systemAlias = ["Automated Finding", "High Confidence Auto-WriteUp Rule", "Medium Confidence Auto-WriteUp Rule"]


    # Get the list of parent/child projects start at the base project
    projectHierarchy = common.api.project.get_child_projects.get_child_projects_recursively(baseURL, projectID, authToken)

        # Create a list of project data sorted by the project name at each level for report display  
    # Add details for the parent node
    nodeDetails = {}
    nodeDetails["parent"] = "#"  # The root node
    nodeDetails["projectName"] = projectHierarchy["name"]
    nodeDetails["projectID"] = projectHierarchy["id"]
    nodeDetails["projectLink"] = baseURL + "/codeinsight/FNCI#myprojectdetails/?id=" + str(projectHierarchy["id"]) + "&tab=projectInventory"

    projectList.append(nodeDetails)

    if includeChildProjects:
        projectList = create_project_hierarchy(projectHierarchy, projectHierarchy["id"], projectList, baseURL)
    else:
        logger.debug("Child hierarchy disabled")

    #  Gather the details for each project and summerize the data
    for project in projectList:

        projectID = project["projectID"]
        projectName = project["projectName"]
        projectLink = project["projectLink"]

        applicationDetails[projectName] = determine_application_details(baseURL, projectName, projectID, authToken)
        applicationNameVersion = applicationDetails[projectName]["applicationNameVersion"]
        
        # Add the applicationNameVersion to the project hierarchy
        project["applicationNameVersion"] = applicationNameVersion

        projectInventory = common.api.project.get_project_inventory.get_project_inventory_details_without_files_or_vulnerabilities(baseURL, projectID, authToken)
        projectInventory = projectInventory["inventoryItems"]

        if not projectInventory:
            logger.warning("    Project contains no inventory items")
            print("Project contains no inventory items.")

        else:
            currentItem=0
            for inventoryItem in projectInventory:

                currentItem +=1
                inventoryID = inventoryItem["id"]
                inventoryItemName = inventoryItem["name"]

                logger.debug("Processing inventory items %s of %s" %(currentItem, len(projectInventory)))
                logger.debug("    Project:  %s   Inventory Name: %s  Inventory ID: %s" %(projectName, inventoryItemName, inventoryID))

                createdOn = inventoryItem["createdOn"]
                createdBy = inventoryItem["createdBy"]
                updatedOn = inventoryItem["updatedOn"] 
                inventoryItemLink = baseURL + '''/codeinsight/FNCI#myprojectdetails/?id=''' + str(projectID) + '''&tab=projectInventory&pinv=''' + str(inventoryID)

                if createdBy in systemAlias:
                    createdBy = "System Created"
                    createdByEmail = False
                else:
                    # Based on login get the other user details
                    userDetails = common.api.users.search_users.get_user_details_by_login(baseURL, authToken, createdBy)
                    createdBy = "%s %s" %(userDetails[0]["firstName"], userDetails[0]["lastName"])
                    createdByEmail = userDetails[0]["email"]
                
                if updatedOn != createdOn:
                    logger.info("This item has changed since creation data")
                    inventoryHistory = common.api.inventory.get_inventory_history.get_inventory_history_details(baseURL, inventoryID, authToken)
                    
                    # In case there was a delay in creating the item see if there is more than one entry in the inventory hisotry
                    if len(inventoryHistory) > 1:

                        # Change the event id to an int to find the max (latest)
                        inventoryHistoryEventIds = {int(k) for k,v in inventoryHistory.items()}
                        latestChangeEventId = str(max(inventoryHistoryEventIds))
                        updatedBy = inventoryHistory[latestChangeEventId][0]["user"]
                        updatedByEmail = inventoryHistory[latestChangeEventId][0]["userEmail"]          
                    else: 
                        logger.info("This item was not changed")
                        updatedOn = ""
                        updatedBy = ""
                        updatedByEmail = False
                else:
                    logger.info("This item was not changed")
                    updatedOn = ""
                    updatedBy = ""
                    updatedByEmail = False

                inventoryDetails[inventoryID] = {}
                inventoryDetails[inventoryID]["inventoryItemName"] = inventoryItemName
                inventoryDetails[inventoryID]["inventoryItemLink"] = inventoryItemLink
                inventoryDetails[inventoryID]["projectName"] = projectName
                inventoryDetails[inventoryID]["projectLink"] = projectLink
                inventoryDetails[inventoryID]["createdOn"] = createdOn
                inventoryDetails[inventoryID]["createdBy"] = createdBy
                inventoryDetails[inventoryID]["createdByEmail"] = createdByEmail
                inventoryDetails[inventoryID]["updatedOn"] = updatedOn
                inventoryDetails[inventoryID]["updatedOn"] = updatedOn
                inventoryDetails[inventoryID]["updatedBy"] = updatedBy
                inventoryDetails[inventoryID]["updatedByEmail"] = updatedByEmail

        # Sort the inventory data by Component Name / Component Version / Selected License Name
    sortedInventoryData = OrderedDict(sorted(inventoryDetails.items(), key=lambda x: (x[1]['inventoryItemName'] )))


    # Build up the data to return for the
    reportData = {}
    reportData["reportName"] = reportName
    reportData["projectList"] = projectList
    reportData["projectHierarchy"] = projectHierarchy
    reportData["primaryProjectName"] = projectHierarchy["name"]
    reportData["inventoryDetails"] = sortedInventoryData

    return reportData


#----------------------------------------------#
def create_project_hierarchy(project, parentID, projectList, baseURL):
    logger.debug("Entering create_project_hierarchy.")
    logger.debug("    Project Details: %s" %project)

    # Are there more child projects for this project?
    if len(project["childProject"]):

        # Sort by project name of child projects
        for childProject in sorted(project["childProject"], key = lambda i: i['name'] ) :

            uniqueProjectID = str(parentID) + "-" + str(childProject["id"])
            nodeDetails = {}
            nodeDetails["projectID"] = childProject["id"]
            nodeDetails["parent"] = parentID
            nodeDetails["uniqueID"] = uniqueProjectID
            nodeDetails["projectName"] = childProject["name"]
            nodeDetails["projectLink"] = baseURL + "/codeinsight/FNCI#myprojectdetails/?id=" + str(childProject["id"]) + "&tab=projectInventory"

            projectList.append( nodeDetails )

            create_project_hierarchy(childProject, uniqueProjectID, projectList, baseURL)

    return projectList
#----------------------------------------------#
def determine_application_details(baseURL, projectName, projectID, authToken):
    logger.debug("Entering determine_application_details.")
    # Create a application name for the report if the custom fields are populated
    # Default values
    applicationName = projectName
    applicationVersion = ""
    applicationPublisher = ""
    applicationDetailsString = ""

    projectInformation = common.api.project.get_project_information.get_project_information_summary(baseURL, projectID, authToken)

    # Project level custom fields added in 2022R1
    if "customFields" in projectInformation:
        customFields = projectInformation["customFields"]

        # See if the custom project fields were propulated for this project
        for customField in customFields:

            # Is there the reqired custom field available?
            if customField["fieldLabel"] == "Application Name":
                if customField["value"]:
                    applicationName = customField["value"]

            # Is the custom version field available?
            if customField["fieldLabel"] == "Application Version":
                if customField["value"]:
                    applicationVersion = customField["value"]     

            # Is the custom Publisher field available?
            if customField["fieldLabel"] == "Application Publisher":
                if customField["value"]:
                    applicationPublisher = customField["value"]    



    # Join the custom values to create the application name for the report artifacts
    if applicationName != projectName:
        if applicationVersion != "":
            applicationNameVersion = applicationName + " - " + applicationVersion
        else:
            applicationNameVersion = applicationName
    else:
        applicationNameVersion = projectName

    if applicationPublisher != "":
        applicationDetailsString += "Publisher: " + applicationPublisher + " | "

    # This will either be the project name or the supplied application name
    applicationDetailsString += "Application: " + applicationName + " | "

    if applicationVersion != "":
        applicationDetailsString += "Version: " + applicationVersion
    else:
        # Rip off the  | from the end of the string if the version was not there
        applicationDetailsString = applicationDetailsString[:-3]

    applicationDetails = {}
    applicationDetails["applicationName"] = applicationName
    applicationDetails["applicationVersion"] = applicationVersion
    applicationDetails["applicationPublisher"] = applicationPublisher
    applicationDetails["applicationNameVersion"] = applicationNameVersion
    applicationDetails["applicationDetailsString"] = applicationDetailsString

    logger.info("    applicationDetails: %s" %applicationDetails)

    return applicationDetails