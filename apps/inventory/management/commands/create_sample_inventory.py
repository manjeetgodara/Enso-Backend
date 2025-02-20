import random
from django.core.management.base import BaseCommand
from inventory.models import ProjectDetail, ProjectTower, Configuration, ProjectInventory, PropertyType

class Command(BaseCommand):
    help = 'Generate sample test data for projects, towers, and flats'

    def handle(self, *args, **kwargs):
        # Create sample projects
        projects = []
        for i in range(1):
            project = ProjectDetail.objects.create(
                name=f'Project {i + 1}',
                description=f'Description for Project {i + 1}',
                rera_number=f'Rera {i + 1}',
                area='1000-1500',
                project_type='Mixed',
                total_towers=4,
                total_units=100,
                address=f'Address for Project {i + 1}',
                city='City',
                state='State',
                pincode='123456',
            )
            projects.append(project)

            property_type_names = ['Flat']

            property_types = []

            for name in property_type_names:
                existing_property_type = PropertyType.objects.filter(name=name).first()
                if existing_property_type:
                    property_types.append(existing_property_type)
                else:
                    new_property_type = PropertyType.objects.create(name=name)
                    property_types.append(new_property_type)

            # Assign property types to projects
            project.properties_type.set(property_types)

            # Create sample towers for each project
            towers = []
            for tower_name in ['A', 'B', 'C', 'D']:
                tower = ProjectTower.objects.create(project=project, name=tower_name)
                towers.append(tower)

                # Create sample configurations
                configurations = []
                for k in ['1BHK', '2BHK', '3BHK']:
                   
                    existing_configuration = Configuration.objects.filter(name=k).first()
                    if existing_configuration:
                        configurations.append(existing_configuration)
                    else:
                        new_configuration = Configuration.objects.create(name=k)
                        configurations.append(new_configuration)

                for floor_number in range(1, 7):
                    for flat_number in range(1, 3):
                        area_choice = random.choice(['<1000 Sqft', '1000-1500 Sqft', '>1500 Sqft'])
                        ProjectInventory.objects.create(
                            tower=tower,
                            configuration=random.choice(configurations),
                            flat_no=f'{floor_number}{0}{flat_number}',
                            floor_number=floor_number,
                            area=area_choice,
                            no_of_bathrooms=2,
                            no_of_bedrooms=3,
                            no_of_balcony=1,
                            vastu_details=f'Vastu details for Flat {flat_number}',
                            pre_deal_amount=800000,
                            min_deal_amount_cm=600000,
                            min_deal_amount_sh=500000,
                            min_deal_amount_vp=400000,
                            status=random.choice(['Yet to book', 'Booked', 'EOI', 'Risk', 'Hold Refuge']),
                            project_inventory_type=random.choice(property_types),
                        )

        self.stdout.write(self.style.SUCCESS('Sample test data created successfully.'))